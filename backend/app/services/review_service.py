"""Expert review business logic (Phase 5).

The one rule that matters here: an AI prediction is never overwritten and never
upgraded into a diagnosis by anything other than this decision path. `ai_predictions`
rows are immutable (Phase 2); this service only ever writes to the observation's own
verification columns (`verification_status`, `final_agent_id`, `verified_by`,
`verified_at`, `review_note`), which is exactly what the database's own
`ck_obs_final_agent_requires_verification` constraint expects.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models.catalog import DiseasePestCatalog
from app.models.observation import Observation
from app.repositories.observation_repository import ObservationRepository
from app.schemas.review import ReviewDecision
from app.services import audit_service as audit_actions
from app.services.audit_service import AuditService

REVIEWABLE_STATUSES = ("PENDING_REVIEW",)

_DECISION_TO_STATUS = {
    "CONFIRM": "CONFIRMED",
    "CORRECT": "CORRECTED",
    "REJECT": "REJECTED",
}


class ReviewService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.observations = ObservationRepository(db)
        self.audit = AuditService(db)

    def get_for_review(self, observation_id: uuid.UUID, user: CurrentUser) -> Observation:
        observation = self.observations.get_for_user(observation_id, user)
        if observation is None:
            raise NotFoundError("Observation")
        return observation

    def queue(
        self, user: CurrentUser, *, page: int, page_size: int
    ) -> tuple[list[Observation], int]:
        return self.observations.review_queue(user, limit=page_size, offset=(page - 1) * page_size)

    def decide(
        self, observation_id: uuid.UUID, user: CurrentUser, payload: ReviewDecision
    ) -> Observation:
        observation = self.get_for_review(observation_id, user)

        if observation.verification_status not in REVIEWABLE_STATUSES:
            raise ConflictError(
                f"Observation is '{observation.verification_status}', not awaiting review.",
                code="OBSERVATION_NOT_REVIEWABLE",
                message_key="errors.observation_not_reviewable",
                details=[{"field": "verification_status", "issue": "not_pending_review"}],
            )

        latest_prediction = self.observations.latest_prediction(observation.id)

        before = {
            "verification_status": observation.verification_status,
            "final_agent_id": str(observation.final_agent_id)
            if observation.final_agent_id
            else None,
        }

        new_status = _DECISION_TO_STATUS[payload.decision]
        final_agent_id: uuid.UUID | None = None

        if payload.decision == "CONFIRM":
            if latest_prediction is None or latest_prediction.predicted_agent_id is None:
                raise ValidationError(
                    "Cannot confirm: there is no AI-predicted agent to confirm.",
                    code="NO_PREDICTION_TO_CONFIRM",
                    message_key="errors.no_prediction_to_confirm",
                )
            final_agent_id = latest_prediction.predicted_agent_id

        elif payload.decision == "CORRECT":
            assert payload.corrected_agent_id is not None  # enforced by the schema
            agent = self.db.get(DiseasePestCatalog, payload.corrected_agent_id)
            if agent is None:
                raise NotFoundError("Disease/pest catalog entry")
            final_agent_id = agent.id

        # REJECT: final_agent_id stays None - the check constraint permits this only
        # for a non-CONFIRMED/CORRECTED status, which REJECTED satisfies.

        observation.verification_status = new_status
        observation.final_agent_id = final_agent_id
        observation.verified_by = user.id
        observation.verified_at = datetime.now(UTC)
        observation.review_note = payload.note
        self.db.flush()

        self.audit.record(
            action=audit_actions.ACTION_OBSERVATION_REVIEWED,
            entity_type="observation",
            entity_id=observation.id,
            actor_user_id=user.id,
            actor_role=user.role.value,
            before_state=before,
            after_state={
                "decision": payload.decision,
                "verification_status": new_status,
                "final_agent_id": str(final_agent_id) if final_agent_id else None,
            },
        )
        return observation
