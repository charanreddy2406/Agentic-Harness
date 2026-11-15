import json
from dataclasses import dataclass
from time import perf_counter

from harness.approval import ApprovalGate
from harness.audit import AuditEntry, AuditLog
from harness.contracts import Message, ToolCall
from harness.models import ModelAdapter
from harness.permissions import Decision, decide, effective_permission
from harness.registry import Registry


@dataclass
class RunResult:
    answer: str
    status: str
    model_calls: int
    tool_calls: int
    model_seconds: float
    elapsed_seconds: float
    audit: list[AuditEntry]


class ToolExecutionError(RuntimeError):
    """The run must stop because a tool's execution outcome is uncertain."""


def execute_call(
    call: ToolCall,
    registry: Registry,
    gate: ApprovalGate,
    audit: AuditLog,
    unattended: bool,
) -> str:
    # Validate untrusted model arguments before approval or execution.
    error = registry.validate(call)
    if error:
        audit.record(call, 'invalid')
        return f'error: {error}'

    tool = registry.get(call.name)
    if tool is None:
        audit.record(call, 'invalid')
        return f'error: unknown tool: {call.name}'

    permission = effective_permission(tool.permission, unattended)
    decision = decide(permission)

    if decision == Decision.BLOCKED:
        audit.record(call, 'blocked')
        return 'blocked: forbidden tool'

    if decision == Decision.NEEDS_APPROVAL:
        try:
            approved = gate.ask(call, permission) is True
        except Exception:
            audit.record(call, 'approval_error')
            return 'denied: approval unavailable'

        audit.record(call, 'approved' if approved else 'denied')
        if not approved:
            return 'denied by human'

    # Drafting must never invoke the handler that commits a side effect.
    handler = tool.draft_handler if decision == Decision.DRAFT else tool.handler
    if handler is None:
        audit.record(call, 'blocked')
        return 'blocked: handler unavailable'

    try:
        output = handler(call.args)
    except Exception as exc:
        audit.record(call, 'handler_error')
        # A handler may have committed a change before raising an exception.
        raise ToolExecutionError(
            'error: tool failed; execution outcome may be uncertain'
        ) from exc

    audit.record(call, 'drafted' if decision == Decision.DRAFT else 'ran')

    try:
        return output if isinstance(output, str) else json.dumps(output, allow_nan=False)
    except (TypeError, ValueError, RecursionError) as exc:
        audit.record(call, 'output_error')
        raise ToolExecutionError(
            'error: tool executed but output could not be serialized'
        ) from exc


def run_agent(
    model: ModelAdapter,
    registry: Registry,
    gate: ApprovalGate,
    task: str,
    max_steps: int = 8,
    max_tool_calls: int = 12,
    unattended: bool = False,
) -> RunResult:
    """Run a bounded model/tool loop with isolated state for each task."""
    if max_steps < 1 or max_tool_calls < 1:
        raise ValueError('Budgets must be positive')

    start = perf_counter()
    model_seconds = 0.0
    model_calls = 0
    tool_calls = 0
    audit = AuditLog()
    seen_ids: set[str] = set()
    messages = [Message(role='user', content=task)]

    def finish(answer: str, status: str) -> RunResult:
        return RunResult(
            answer=answer,
            status=status,
            model_calls=model_calls,
            tool_calls=tool_calls,
            model_seconds=model_seconds,
            elapsed_seconds=perf_counter() - start,
            audit=list(audit.entries),
        )

    for _ in range(max_steps):
        model_calls += 1
        before = perf_counter()
        try:
            response = model.complete(messages, registry.specs_for_model(unattended))
        except Exception:
            model_seconds += perf_counter() - before
            return finish('error: model call failed', 'model_error')
        model_seconds += perf_counter() - before

        # A response without tool calls ends the agent loop.
        if not response.tool_calls:
            return finish(response.text or '(no answer)', 'finished')

        # Reject an entire batch before running any part of it if over budget.
        if tool_calls + len(response.tool_calls) > max_tool_calls:
            for call in response.tool_calls:
                audit.record(call, 'budget_blocked')
            return finish('(stopped: tool-call ceiling)', 'tool_limit')

        ids = [call.id for call in response.tool_calls]
        if any(not i or i in seen_ids for i in ids) or len(set(ids)) != len(ids):
            for call in response.tool_calls:
                audit.record(call, 'invalid_call_id')
            return finish('(stopped: duplicate or empty call ID)', 'protocol_error')
        seen_ids.update(ids)

        # Preserve the assistant's tool requests so results can reference them.
        messages.append(Message('assistant', response.text, response.tool_calls))

        for index, call in enumerate(response.tool_calls):
            tool_calls += 1
            try:
                result = execute_call(call, registry, gate, audit, unattended)
            except ToolExecutionError as exc:
                # Do not let the model retry an action with an uncertain outcome.
                for pending in response.tool_calls[index + 1:]:
                    audit.record(pending, 'skipped_after_error')
                return finish(str(exc), 'tool_error')

            messages.append(Message('tool', result, tool_call_id=call.id))

    return finish('(stopped: model-step ceiling)', 'step_limit')
