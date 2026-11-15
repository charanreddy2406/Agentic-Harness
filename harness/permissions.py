from enum import Enum

from harness.contracts import Permission


class Decision(str, Enum):
    RUN = 'run'
    DRAFT = 'draft'
    NEEDS_APPROVAL = 'needs_approval'
    BLOCKED = 'blocked'


def effective_permission(base: Permission, unattended: bool = False) -> Permission:
    """Unattended runs can tighten permissions, never relax them."""
    if unattended and base in (Permission.APPROVAL_REQUIRED, Permission.DANGEROUS):
        return Permission.FORBIDDEN
    return base


def decide(permission: Permission) -> Decision:
    """Translate the effective permission into a runtime action."""
    if permission == Permission.READ_ONLY:
        return Decision.RUN
    if permission == Permission.DRAFT_ONLY:
        return Decision.DRAFT
    if permission in (Permission.APPROVAL_REQUIRED, Permission.DANGEROUS):
        return Decision.NEEDS_APPROVAL
    return Decision.BLOCKED
