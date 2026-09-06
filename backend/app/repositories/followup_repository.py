"""Follow-up data access (Phase 7).

Visibility is derived by joining to the PARENT observation and reusing
`ObservationRepository.apply_scope` - the same farmer/district/admin rule every other
observation-bearing query already follows, so a farmer cannot see another farmer's
follow-ups and an extension worker is bounded by their own district exactly as with
observations and reviews.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.models.followup import Followup
from app.models.observation import Observation
from app.repositories.observation_repository import ObservationRepository


class FollowupRepository:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.observations = ObservationRepository(db)

    def _scoped(self, stmt: Select, user: CurrentUser) -> Select:
        stmt = stmt.join(Observation, Observation.id == Followup.parent_observation_id)
        return self.observations.apply_scope(stmt, user)

    def get_for_user(self, followup_id: uuid.UUID, user: CurrentUser) -> Followup | None:
        stmt = self._scoped(select(Followup).where(Followup.id == followup_id), user)
        return self.db.execute(stmt).scalars().first()

    def list_for_user(
        self,
        user: CurrentUser,
        *,
        observation_id: uuid.UUID | None = None,
        outcome: str | None = None,
        status: str | None = None,
        include_demo: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Followup], int]:
        """`include_demo=False` (the default) excludes follow-ups on a
        DEMO_SIMULATION observation from a district-wide LISTING (expert triage,
        official dashboard) - simulated data must not mix into a real list unless
        explicitly asked for, exactly like every GIS/dashboard query already behaves.
        It never applies when `observation_id` is given: a caller asking for one
        specific observation's own follow-up history already has access to that
        observation (checked via `_scoped`) and must see its real history whether or
        not that observation itself happens to be demo data - hiding it there would
        break the demo's own follow-up display, not protect anyone. A farmer's own
        follow-ups are unaffected either way (scoped to their own farmer_id, which a
        demo account never shares)."""
        stmt = self._scoped(select(Followup), user)
        if observation_id is not None:
            stmt = stmt.where(Followup.parent_observation_id == observation_id)
        if outcome is not None:
            stmt = stmt.where(Followup.outcome == outcome)
        if status is not None:
            stmt = stmt.where(Followup.status == status)
        if not include_demo and observation_id is None:
            stmt = stmt.where(Observation.source_type != "DEMO_SIMULATION")

        count_stmt = self._scoped(select(Followup.id), user)
        if observation_id is not None:
            count_stmt = count_stmt.where(Followup.parent_observation_id == observation_id)
        if outcome is not None:
            count_stmt = count_stmt.where(Followup.outcome == outcome)
        if status is not None:
            count_stmt = count_stmt.where(Followup.status == status)
        if not include_demo and observation_id is None:
            count_stmt = count_stmt.where(Observation.source_type != "DEMO_SIMULATION")
        total_count = len(self.db.execute(count_stmt).all())

        rows = list(
            self.db.execute(
                stmt.order_by(Followup.scheduled_for.asc()).limit(limit).offset(offset)
            ).scalars()
        )
        return rows, total_count

    def for_observation(self, observation_id: uuid.UUID) -> list[Followup]:
        """Unscoped - used only by callers (advisory/review detail) that have already
        confirmed the caller may see the parent observation."""
        return list(
            self.db.execute(
                select(Followup)
                .where(Followup.parent_observation_id == observation_id)
                .order_by(Followup.scheduled_for.desc())
            ).scalars()
        )

    def create(
        self,
        *,
        parent_observation_id: uuid.UUID,
        scheduled_for: datetime,
        created_by: uuid.UUID,
    ) -> Followup:
        followup = Followup(
            parent_observation_id=parent_observation_id,
            scheduled_for=scheduled_for,
            created_by=created_by,
        )
        self.db.add(followup)
        self.db.flush()
        return followup
