import json
from collections.abc import Callable
from typing import Protocol
from harness.contracts import Permission, ToolCall


class ApprovalGate(Protocol):
    def ask(self, call: ToolCall, permission: Permission) -> bool: ...


class CliApproval:
    def __init__(self, prompt: Callable[[str], str] = input) -> None:
        self.prompt = prompt

    def ask(self, call: ToolCall, permission: Permission) -> bool:
        print(f'\nApproval required: {call.name}')
        print(json.dumps(call.args, indent=2, ensure_ascii=True))
        # Stronger confirmation is based on permission, not the tool name.
        if permission == Permission.DANGEROUS:
            return self.prompt(f'Type {call.name} to confirm: ').strip() == call.name
        return self.prompt('Approve? [y/N]: ').strip().lower() == 'y'
