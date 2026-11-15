from harness.contracts import Permission, Tool, ToolSpec


def schema(*keys: str) -> dict:
    """Build a schema for the supported required string arguments."""
    return {
        'type': 'object',
        'properties': {key: {'type': 'string'} for key in keys},
        'required': list(keys),
        'additionalProperties': False,
    }


# These handlers are simulations; no external system is modified.
def list_files(args: dict) -> list[str]:
    return ['README.md', 'bug_report.txt', 'owner.txt']


def send_email(args: dict) -> str:
    return f"[SIMULATED SEND] to={args['to']} subject={args['subject']}"


def delete_repo(args: dict) -> str:
    return f"[SIMULATED DELETE] repo={args['repo']}"


def draft_email(args: dict) -> str:
    return f"[DRAFT — not sent] To: {args['to']}\nSubject: {args['subject']}\n{args['body']}"


def example_tools() -> list[Tool]:
    email_schema = schema('to', 'subject', 'body')
    return [
        Tool(
            spec=ToolSpec('list_files', 'List example project files.', schema()),
            permission=Permission.READ_ONLY,
            handler=list_files,
        ),
        Tool(
            spec=ToolSpec('send_email', 'Simulate sending an email.', email_schema),
            permission=Permission.APPROVAL_REQUIRED,
            handler=send_email,
        ),
        Tool(
            spec=ToolSpec('delete_repo', 'Simulate deleting an entire repository.', schema('repo')),
            permission=Permission.DANGEROUS,
            handler=delete_repo,
        ),
        Tool(
            spec=ToolSpec('draft_email', 'Prepare an email without sending it.', email_schema),
            permission=Permission.DRAFT_ONLY,
            draft_handler=draft_email,
        ),
    ]
