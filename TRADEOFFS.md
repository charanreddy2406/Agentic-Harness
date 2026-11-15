# Migration decisions

| TypeScript source | Python replacement |
|---|---|
| types.ts / adapters/adapter.ts | contracts.py and models.py |
| tools/registry.ts | registry.py |
| tools/examples.ts | tools.py |
| adapters/openaiAdapter.ts / localAdapter.ts | models.py (OpenAI-compatible adapter plus deterministic demo) |
| loop/run.ts | agent.py |
| permissions/engine.ts / policy.ts | permissions.py (policy and decision engine); agent.py enforces the decision |
| approval/cliGate.ts | approval.py |
| audit/log.ts | audit.py |
| Missing entry point/tests | main.py and tests/test_harness.py |

Synchronous Python intentionally replaces async TypeScript: one task and sequential tool calls are sufficient for the learning objective. Async is a future throughput choice, not required for correctness. The original local adapter assumed a hypothetical format; the Python version instead supports OpenAI-compatible servers, not arbitrary local protocols. No agent framework is required.

Improvements: restricted-schema validation with type checks, duplicate registration checks, integrated unattended policy, distinct draft handler, exact human confirmation based on permission level, assistant tool-call history, bounded call count, model timing, per-run audit with call IDs and timestamps, and explicit error observations, and termination on uncertain tool outcomes. These are not a substitute for production controls. See README for limits.
