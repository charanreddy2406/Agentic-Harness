# Agentic Harness — Python

A model-agnostic, governed agent runtime, migrated from the supplied TypeScript capstone. The model proposes tool calls; deterministic Python controls validation, permissions, approvals, execution, and audit. All example tools are simulations, never real email or repository operations.

## Run (Python 3.10+)

No packages, account, API key, or subscription are needed for the default demo.

```bash
python3 main.py
python3 main.py --case email
python3 main.py --case delete
python3 main.py --case draft
python3 main.py --case email --unattended
python3 -m unittest discover -v
```

The default run uses a deterministic DemoModel, not a language model. The selected case supplies a prewritten tool call; the next response echoes the actual tool observation. Ordinary approval requires `y`; dangerous approval requires the exact tool name. Any other input denies. Unattended runs block approval-required and dangerous tools.

## Optional actual model

```bash
python3 -m pip install -e '.[live]'
export OPENAI_API_KEY='YOUR_KEY'
python3 main.py --model YOUR_TOOL_CAPABLE_MODEL --task 'Show me the project files.'
```

Use a model available to your account. This path uses the SDK's Chat Completions tool protocol, with a 30-second client timeout and no automatic SDK retries. A compatible local server can be configured with `OPENAI_BASE_URL` and its required key; it must support the same tool-calling protocol. Live provider calls were not performed. API usage may incur charges. Never commit a key. The examples remain simulated even with a real model.


## Scope

This is a synchronous learning runtime, not a production security boundary. It validates a deliberately restricted subset of JSON Schema (flat objects, required nonempty strings, no extra fields). Email addresses are not semantically validated. Trusted developers provide handlers; the runtime does not sandbox them. Audit is per-run and in memory, excludes argument values, and is not durable. Model-call and tool-call ceilings are implemented; hard cost/token/wall-clock budgets, persistent memory, real connectors, durable approvals, cross-run idempotency and deployment are not. Duplicate call IDs are rejected within a run, but different IDs can still request the same action. If a handler raises or its output cannot be serialized, the run stops and remaining calls are skipped; an uncertain side effect is not automatically retried by this run. Model-produced final text is not independently verified. The original source is left untouched.
