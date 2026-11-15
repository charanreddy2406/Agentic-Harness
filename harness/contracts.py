"""Shared data contracts used by every component of the harness."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class Permission(str, Enum):
    READ_ONLY = 'read-only'
    DRAFT_ONLY = 'draft-only'
    APPROVAL_REQUIRED = 'approval-required'
    DANGEROUS = 'dangerous'
    FORBIDDEN = 'forbidden'


@dataclass(frozen=True)
class ToolCall:
    # Provider-independent representation of a proposed action.
    id: str
    name: str
    args: Any
    raw_arguments: str | None = None


@dataclass
class ModelResponse:
    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict


@dataclass(frozen=True)
class Tool:
    # Specifications are exposed to the model; handlers are not.
    spec: ToolSpec
    permission: Permission
    handler: Callable[[dict], Any] | None = None
    draft_handler: Callable[[dict], Any] | None = None


@dataclass
class Message:
    role: str
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None
