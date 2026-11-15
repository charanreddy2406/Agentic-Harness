from harness.contracts import Permission, Tool, ToolCall, ToolSpec
from harness.permissions import effective_permission


class Registry:
    """Store trusted tool definitions and validate proposed calls."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        name = tool.spec.name
        if not name or name in self._tools:
            raise ValueError(f'Invalid or duplicate tool name: {name}')

        # This runtime supports only flat objects with required string fields.
        schema = tool.spec.input_schema
        properties = schema.get('properties')
        required = schema.get('required')
        if (
            schema.get('type') != 'object'
            or set(schema) != {'type', 'properties', 'required', 'additionalProperties'}
            or schema.get('additionalProperties') is not False
            or not isinstance(properties, dict)
            or not isinstance(required, list)
            or any(not isinstance(key, str) for key in required)
            or len(required) != len(set(required))
            or set(required) != set(properties)
            or any(value != {'type': 'string'} for value in properties.values())
        ):
            raise ValueError('Unsupported tool schema')

        if not isinstance(tool.permission, Permission):
            raise ValueError('Invalid permission')
        if tool.permission == Permission.DRAFT_ONLY:
            if not callable(tool.draft_handler):
                raise ValueError('Draft tool requires a separate draft handler')
        elif tool.permission != Permission.FORBIDDEN and not callable(tool.handler):
            raise ValueError('Executable tool requires a handler')

        self._tools[name] = tool

    def specs_for_model(self, unattended: bool = False) -> list[ToolSpec]:
        # Hide forbidden tools; execution still checks permissions independently.
        return [
            tool.spec
            for tool in self._tools.values()
            if effective_permission(tool.permission, unattended) != Permission.FORBIDDEN
        ]

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def validate(self, call: ToolCall) -> str | None:
        tool = self.get(call.name)
        if tool is None:
            return f'unknown tool: {call.name}'
        if not isinstance(call.args, dict):
            return 'arguments must be a JSON object'

        schema = tool.spec.input_schema
        for key in schema['required']:
            if key not in call.args:
                return f'missing required arg: {key}'

        for key, value in call.args.items():
            if key not in schema['properties']:
                return f'unexpected arg: {key}'
            if not isinstance(value, str):
                return f'arg {key} must be a string'
            if not value.strip():
                return f'arg {key} must not be empty'

        return None  # No validation error; permission checks come next.
