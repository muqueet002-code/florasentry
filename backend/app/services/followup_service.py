"""Follow-up business logic (Phase 7).

Submitting a follow-up REUSES the full existing observation pipeline
(`ObservationService.create_with_image`) rather than building a second one: image
validation, storage, AI inference and the confidence gate, weather and risk all run
exactly as they do for a first-time report. No second AI system exists.

The only thing this module adds on top of that reused pipeline is linking the new
observation back to its parent via `parent_observation_id` - a column that has existed
on `observations` since Phase 1 for exactly this purpose. The parent observation and
its own prediction/verification_status/final_agent_id are never modified.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.config import settings
from app.core.errors import ConflictError, NotFoundError, OwnershipError
from app.core.rbac import UserRole
from app.models.followup import Followup
from app.models.observation import Observation
from app.repositories.followup_repository import FollowupRepository
from app.repositories.observation_repository import ObservationRepository
from app.schemas.observation import ObservationCreate
from app.services.audit_service import AuditService
from app.services.observation_service import ObservationService, PipelineOutcome

ACTION_FOLLOWUP_CREATED = "FOLLOWUP_CREATED"
ACTION_FOLLOWUP_SUBMITTED = "FOLLOWUP_SUBMITTED"

_DAYS_BY_RISK = {
    "HIGH": lambda: settings.FOLLOWUP_DAYS_HIGH,
    "MEDIUM": lambda: settings.FOLLOWUP_DAYS_MEDIUM,
    "LOW": lambda: settings.FOLLOWUP_DAYS_LOW,
}


class FollowupService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.followups = FollowupRepository(db)
        self.observations = ObservationRepository(db)
        self.audit = AuditService(db)

    @staticmethod
    def _assert_can_act_on(user: CurrentUser, parent: Observation) -> None:
        if user.role is UserRole.ADMIN:
            return
        if user.farmer_id is not None and parent.farmer_id == user.farmer_id:
            return
        if user.role is UserRole.EXTENSION_WORKER:
            return  # scope already narrowed to their district by the repository query
        raise OwnershipError()

    def _default_interval_days(self, observation_id: uuid.UUID) -> int:
        risk = self.observations.latest_risk(observation_id)
        if risk is None:
            return settings.FOLLOWUP_DAYS_DEFAULT
        return _DAYS_BY_RISK.get(risk.risk_level, lambda: settings.FOLLOWUP_DAYS_DEFAULT)()

    def create(
        self, *, user: CurrentUser, observation_id: uuid.UUID, scheduled_for: datetime | None
    ) -> Followup:
        parent = self.observations.get_for_user(observation_id, user)
        if parent is None:
            raise NotFoundError("Observation")
        self._assert_can_act_on(user, parent)

        due = scheduled_for or (
            datetime.now(UTC) + timedelta(days=self._default_interval_days(parent.id))
        )
        followup = self.followups.create(
            parent_observation_id=parent.id, scheduled_for=due, created_by=user.id
        )
        self.audit.record(
            action=ACTION_FOLLOWUP_CREATED,
            entity_type="followup",
            entity_id=followup.id,
            actor_user_id=user.id,
            actor_role=user.role.value,
            after_state={"parent_observation_id": str(parent.id), "scheduled_for": due.isoformat()},
        )
        return followup

    def get_for_user(self, followup_id: uuid.UUID, user: CurrentUser) -> Followup:
        followup = self.followups.get_for_user(followup_id, user)
        if followup is None:
            raise NotFoundError("Followup")
        return followup

    def submit(
        self,
        *,
        followup_id: uuid.UUID,
        user: CurrentUser,
        outcome: str,
        notes: str | None,
        image_bytes: bytes | None,
        declared_mime: str | None,
    ) -> tuple[Followup, PipelineOutcome]:
        followup = self.get_for_user(followup_id, user)
        parent = self.db.get(Observation, followup.parent_observation_id)
        assert parent is not None  # FK guarantees this
        self._assert_can_act_on(user, parent)

        if followup.status == "SUBMITTED":
            raise ConflictError(
                "This follow-up has already been submitted.",
                code="FOLLOWUP_ALREADY_SUBMITTED",
                message_key="errors.followup_already_submitted",
            )

        # The image is always optional (TRD Part E): reuse the same ObservationCreate
        # validation and the same pipeline either way, differing only in
        # observation_type. This always produces a real linked observation - carrying
        # fresh weather/risk even for a note-only submission - through code that is
        # already exercised by the first-time report path.
        payload = ObservationCreate(
            field_id=parent.field_id,
            crop_id=parent.crop_id,
            variety_id=parent.variety_id,
            growth_stage_id=parent.growth_stage_id,
            observation_type="IMAGE" if image_bytes else "MANUAL_REPORT",
            latitude=float(parent.latitude),
            longitude=float(parent.longitude),
            location_method=parent.location_method,  # type: ignore[arg-type]
            reported_severity=parent.reported_severity,
            notes=notes,
        )
        pipeline_outcome = ObservationService(self.db).create_with_image(
            user_id=user.id,
            farmer_id=parent.farmer_id,
            payload=payload,
            image_bytes=image_bytes,
            declared_mime=declared_mime,
        )
        # Link back to the parent. This NEVER touches the parent's own prediction,
        # verification_status or final_agent_id.
        pipeline_outcome.observation.parent_observation_id = parent.id
        self.db.flush()
        followup.followup_observation_id = pipeline_outcome.observation.id

        followup.outcome = outcome
        followup.notes = notes
        followup.status = "SUBMITTED"
        followup.submitted_by = user.id
        followup.submitted_at = datetime.now(UTC)
        self.db.flush()

        self.audit.record(
            action=ACTION_FOLLOWUP_SUBMITTED,
            entity_type="followup",
            entity_id=followup.id,
            actor_user_id=user.id,
            actor_role=user.role.value,
            after_state={
                "outcome": outcome,
                "followup_observation_id": (
                    str(followup.followup_observation_id)
                    if followup.followup_observation_id
                    else None
                ),
            },
        )
        return followup, pipeline_outcome
