import json
from typing import Any, Protocol

from harness.contracts import Message, ModelResponse, ToolCall, ToolSpec


class ModelAdapter(Protocol):
    """All model providers implement the same interface."""

    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> ModelResponse:
        ...


class ScriptedModel:
    """Deterministic test double, not a language model."""

    def __init__(self, responses: list[ModelResponse]) -> None:
        self.responses = iter(responses)

    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> ModelResponse:
        return next(self.responses)


class OpenAICompatibleModel:
    """Translate the common harness contracts into the provider's tool protocol."""

    def __init__(self, client: Any, model: str) -> None:
        self.client = client
        self.model = model

    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> ModelResponse:
        history: list[dict] = []
        for message in messages:
            item: dict = {'role': message.role, 'content': message.content}
            if message.tool_calls:
                item['tool_calls'] = [
                    {
                        'id': call.id,
                        'type': 'function',
                        'function': {
                            'name': call.name,
                            # Preserve the original provider arguments for replay.
                            'arguments': (
                                call.raw_arguments
                                if call.raw_arguments is not None
                                else json.dumps(call.args)
                            ),
                        },
                    }
                    for call in message.tool_calls
                ]
            if message.tool_call_id is not None:
                item['tool_call_id'] = message.tool_call_id
            history.append(item)

        request: dict = {'model': self.model, 'messages': history}
        if tools:
            request['tools'] = [
                {
                    'type': 'function',
                    'function': {
                        'name': tool.name,
                        'description': tool.description,
                        'parameters': tool.input_schema,
                    },
                }
                for tool in tools
            ]

        response = self.client.chat.completions.create(**request)
        choice = response.choices[0].message
        calls = []
        for call in choice.tool_calls or []:
            raw = call.function.arguments
            try:
                args = json.loads(raw)
            except (ValueError, TypeError):
                args = None  # The registry will reject malformed arguments.
            calls.append(ToolCall(call.id, call.function.name, args, raw))

        return ModelResponse(text=choice.content, tool_calls=calls)


class DemoModel:
    """Request one scripted action, then echo its actual tool result."""

    def __init__(self, call: ToolCall) -> None:
        self.call = call

    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> ModelResponse:
        if messages[-1].role == 'tool':
            return ModelResponse(text=messages[-1].content)
        return ModelResponse(tool_calls=[self.call])
