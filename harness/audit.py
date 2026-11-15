from dataclasses import dataclass
from datetime import datetime, timezone
from harness.contracts import ToolCall


@dataclass(frozen=True)
class AuditEntry:
    timestamp: str
    call_id: str
    tool: str
    outcome: str


class AuditLog:
    """Per-run audit trail; do not store sensitive tool argument values."""

    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    def record(self, call: ToolCall, outcome: str) -> None:
        self.entries.append(AuditEntry(
            datetime.now(timezone.utc).isoformat(), call.id, call.name, outcome
        ))
