"""Business audit trail (TRD 5.17, 33.1).

Separate from operational logging: this answers "who did what to this record?" and is
append-only, long-lived and access-controlled.

Failure policy (TRD 5.17): for a security-relevant action the audit write is part of
the caller's transaction, so a failure aborts the operation. It is never swallowed.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.logging import get_logger, redact, trace_id_ctx
from app.models.provenance import AuditLog

logger = get_logger(__name__)

# Security-relevant actions (TRD 29.10).
ACTION_REGISTER = "USER_REGISTERED"
ACTION_LOGIN_SUCCESS = "LOGIN_SUCCESS"
ACTION_LOGIN_FAILURE = "LOGIN_FAILURE"
ACTION_LOGOUT = "LOGOUT"
ACTION_TOKEN_REFRESH = "TOKEN_REFRESHED"
ACTION_TOKEN_REUSE_DETECTED = "REFRESH_TOKEN_REUSE_DETECTED"
ACTION_PASSWORD_CHANGED = "PASSWORD_CHANGED"
ACTION_ROLE_CHANGED = "ROLE_CHANGED"
ACTION_USER_DEACTIVATED = "USER_DEACTIVATED"
ACTION_FIELD_CREATED = "FIELD_CREATED"
ACTION_FIELD_UPDATED = "FIELD_UPDATED"
ACTION_FIELD_DELETED = "FIELD_DELETED"
ACTION_OBSERVATION_REVIEWED = "OBSERVATION_REVIEWED"


class AuditService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        *,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID | None = None,
        actor_user_id: uuid.UUID | None = None,
        actor_role: str | None = None,
        before_state: dict[str, Any] | None = None,
        after_state: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """Append one audit row. State payloads are redacted before storage."""
        entry = AuditLog(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            before_state=redact(before_state) if before_state else None,
            after_state=redact(after_state) if after_state else None,
            ip_address=ip_address,
            user_agent=user_agent[:1000] if user_agent else None,
            trace_id=trace_id_ctx.get(),
        )
        self.db.add(entry)
        self.db.flush()
        logger.info(
            "audit_recorded",
            extra={"action": action, "entity_type": entity_type, "entity_id": str(entity_id)},
        )
        return entry
