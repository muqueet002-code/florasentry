"""Observation data access (Phase 2 + 3 + 4/5).

Role scoping lives here, so a new endpoint inherits it rather than re-implementing it.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import Select, case, cast, func, select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.rbac import UserRole
from app.models.farmer import Field
from app.models.observation import Observation, ObservationImage
from app.models.prediction import AiPrediction
from app.models.risk import RiskAssessment


class ObservationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ---- scoping ----

    def _scoped(self, stmt: Select, user: CurrentUser) -> Select:
        stmt = stmt.where(Observation.deleted_at.is_(None))
        if user.role is UserRole.ADMIN:
            return stmt
        if user.role is UserRole.FARMER:
            return stmt.where(Observation.farmer_id == (user.farmer_id or uuid.UUID(int=0)))
        if user.role in (UserRole.EXTENSION_WORKER, UserRole.OFFICIAL):
            if user.district_code:
                return stmt.where(Observation.district_code == user.district_code)
            return stmt
        if user.role is UserRole.LAB_EXPERT:
            # Lab experts see only referred cases (the referral workflow itself is a
            # later phase; this scope was already in place before Phase 5).
            return stmt.where(Observation.verification_status == "LAB_REFERRED")
        return stmt.where(func.false())

    def apply_scope(self, stmt: Select, user: CurrentUser) -> Select:
        """Public entry point so other modules (GIS, hotspots) inherit the same rule
        rather than re-implementing per-role visibility."""
        return self._scoped(stmt, user)

    # ---- reads ----

    def get_for_user(self, observation_id: uuid.UUID, user: CurrentUser) -> Observation | None:
        stmt = self._scoped(select(Observation).where(Observation.id == observation_id), user)
        return self.db.execute(stmt).scalars().first()

    def list_for_user(
        self, user: CurrentUser, *, limit: int, offset: int
    ) -> tuple[list[Observation], int]:
        base = self._scoped(select(Observation), user)
        total = self.db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
        rows = list(
            self.db.execute(
                base.order_by(Observation.observed_at.desc()).limit(limit).offset(offset)
            ).scalars()
        )
        return rows, int(total)

    def primary_image(self, observation_id: uuid.UUID) -> ObservationImage | None:
        return (
            self.db.execute(
                select(ObservationImage)
                .where(ObservationImage.observation_id == observation_id)
                .order_by(ObservationImage.is_primary.desc(), ObservationImage.created_at)
                .limit(1)
            )
            .scalars()
            .first()
        )

    def get_image(self, image_id: uuid.UUID) -> ObservationImage | None:
        return self.db.get(ObservationImage, image_id)

    def latest_prediction(self, observation_id: uuid.UUID) -> AiPrediction | None:
        """Predictions are immutable; a re-run inserts a new row, so take the newest."""
        return (
            self.db.execute(
                select(AiPrediction)
                .where(AiPrediction.observation_id == observation_id)
                .order_by(AiPrediction.created_at.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )

    def latest_risk(self, observation_id: uuid.UUID) -> RiskAssessment | None:
        return (
            self.db.execute(
                select(RiskAssessment)
                .where(RiskAssessment.observation_id == observation_id)
                .order_by(RiskAssessment.computed_at.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )

    def latest_predictions_bulk(
        self, observation_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, AiPrediction]:
        """One query for many observations, avoiding N+1 on a map/list view."""
        if not observation_ids:
            return {}
        ranked = (
            select(
                AiPrediction,
                func.row_number()
                .over(
                    partition_by=AiPrediction.observation_id,
                    order_by=AiPrediction.created_at.desc(),
                )
                .label("rn"),
            )
            .where(AiPrediction.observation_id.in_(observation_ids))
            .subquery()
        )
        rows = self.db.execute(
            select(AiPrediction)
            .select_from(ranked)
            .join(AiPrediction, AiPrediction.id == ranked.c.id)
            .where(ranked.c.rn == 1)
        ).scalars()
        return {p.observation_id: p for p in rows}

    def latest_risk_bulk(self, observation_ids: list[uuid.UUID]) -> dict[uuid.UUID, RiskAssessment]:
        if not observation_ids:
            return {}
        ranked = (
            select(
                RiskAssessment,
                func.row_number()
                .over(
                    partition_by=RiskAssessment.observation_id,
                    order_by=RiskAssessment.computed_at.desc(),
                )
                .label("rn"),
            )
            .where(RiskAssessment.observation_id.in_(observation_ids))
            .subquery()
        )
        rows = self.db.execute(
            select(RiskAssessment)
            .select_from(ranked)
            .join(RiskAssessment, RiskAssessment.id == ranked.c.id)
            .where(ranked.c.rn == 1)
        ).scalars()
        return {r.observation_id: r for r in rows if r.observation_id is not None}

    # ---- GIS (Phase 4) ----

    def query_bbox(
        self,
        user: CurrentUser,
        *,
        bbox: tuple[float, float, float, float],
        crop_id: uuid.UUID | None = None,
        agent_id: uuid.UUID | None = None,
        verification_status: str | None = None,
        risk_level: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        include_demo: bool = False,
        limit: int = 2000,
    ) -> list[Observation]:
        """Bounded map query. `bbox` is required by every caller - the guardrail lives
        in the API layer so it applies uniformly, not per-repository-method."""
        minx, miny, maxx, maxy = bbox
        stmt = self._scoped(select(Observation), user).where(
            func.ST_Intersects(Observation.geom, func.ST_MakeEnvelope(minx, miny, maxx, maxy, 4326))
        )
        if crop_id is not None:
            stmt = stmt.where(Observation.crop_id == crop_id)
        if verification_status is not None:
            stmt = stmt.where(Observation.verification_status == verification_status)
        if date_from is not None:
            stmt = stmt.where(Observation.observed_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(Observation.observed_at <= date_to)
        if not include_demo:
            stmt = stmt.where(Observation.source_type != "DEMO_SIMULATION")

        if agent_id is not None:
            # Match either the expert-confirmed diagnosis or (absent that) the latest
            # AI prediction - `agent_for()` in the hotspot module applies the same rule.
            latest_pred_agent = (
                select(AiPrediction.predicted_agent_id)
                .where(AiPrediction.observation_id == Observation.id)
                .order_by(AiPrediction.created_at.desc())
                .limit(1)
                .correlate(Observation)
                .scalar_subquery()
            )
            stmt = stmt.where(
                case(
                    (Observation.final_agent_id.is_not(None), Observation.final_agent_id),
                    else_=latest_pred_agent,
                )
                == agent_id
            )

        if risk_level is not None:
            latest_risk_level = (
                select(RiskAssessment.risk_level)
                .where(RiskAssessment.observation_id == Observation.id)
                .order_by(RiskAssessment.computed_at.desc())
                .limit(1)
                .correlate(Observation)
                .scalar_subquery()
            )
            stmt = stmt.where(latest_risk_level == risk_level)

        stmt = stmt.order_by(Observation.observed_at.desc()).limit(limit)
        return list(self.db.execute(stmt).scalars())

    def query_nearby(
        self,
        user: CurrentUser,
        *,
        latitude: float,
        longitude: float,
        radius_m: int,
        window_days: int | None = None,
        include_demo: bool = False,
        limit: int = 500,
    ) -> list[Observation]:
        """PostGIS radius query (`ST_DWithin` on geography, so the radius is real
        metres). Same pattern as the risk engine's nearby-history query."""
        point = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)
        stmt = self._scoped(select(Observation), user).where(
            func.ST_DWithin(cast(Observation.geom, Geography), cast(point, Geography), radius_m)
        )
        if window_days is not None:
            since = datetime.now(UTC) - timedelta(days=window_days)
            stmt = stmt.where(Observation.observed_at >= since)
        if not include_demo:
            stmt = stmt.where(Observation.source_type != "DEMO_SIMULATION")

        stmt = stmt.order_by(
            func.ST_Distance(cast(Observation.geom, Geography), cast(point, Geography))
        ).limit(limit)
        return list(self.db.execute(stmt).scalars())

    # ---- dashboard (Phase 8) ----
    # Every method below is a read aggregate over data already produced by Phases
    # 1-7 - no new counters or classifications are invented, and every query goes
    # through `_scoped` exactly like the rest of this repository, so an OFFICIAL
    # sees only their own district, identically to the map.

    def _latest_risk_level_subquery(self):
        return (
            select(RiskAssessment.risk_level)
            .where(RiskAssessment.observation_id == Observation.id)
            .order_by(RiskAssessment.computed_at.desc())
            .limit(1)
            .correlate(Observation)
            .scalar_subquery()
        )

    def dashboard_stats(self, user: CurrentUser, *, include_demo: bool = False) -> dict[str, int]:
        """Overview counters: total, high-risk, pending review, confirmed/corrected."""
        base = self._scoped(select(Observation), user)
        if not include_demo:
            base = base.where(Observation.source_type != "DEMO_SIMULATION")

        def _count(stmt: Select) -> int:
            return int(
                self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
            )

        return {
            "total_observations": _count(base),
            "high_risk_observations": _count(
                base.where(self._latest_risk_level_subquery() == "HIGH")
            ),
            "pending_expert_reviews": _count(
                base.where(Observation.verification_status.in_(("PENDING_REVIEW", "LAB_REFERRED")))
            ),
            "confirmed_cases": _count(
                base.where(Observation.verification_status.in_(("CONFIRMED", "CORRECTED")))
            ),
        }

    def agent_frequency(
        self, user: CurrentUser, *, limit: int = 8, include_demo: bool = False
    ) -> list[dict[str, Any]]:
        """Most frequently observed threats.

        An observation counts toward its expert-confirmed agent when set, else its
        latest AI prediction - the same resolution rule `query_bbox`/hotspots use, so
        this summary never disagrees with the map.
        """
        latest_pred_agent = (
            select(AiPrediction.predicted_agent_id)
            .where(AiPrediction.observation_id == Observation.id)
            .order_by(AiPrediction.created_at.desc())
            .limit(1)
            .correlate(Observation)
            .scalar_subquery()
        )
        resolved_agent = case(
            (Observation.final_agent_id.is_not(None), Observation.final_agent_id),
            else_=latest_pred_agent,
        ).label("resolved_agent_id")
        is_confirmed = case(
            (Observation.verification_status.in_(("CONFIRMED", "CORRECTED")), 1), else_=0
        ).label("is_confirmed")

        base = self._scoped(select(Observation), user)
        if not include_demo:
            base = base.where(Observation.source_type != "DEMO_SIMULATION")
        sub = base.add_columns(resolved_agent, is_confirmed).subquery()

        stmt = (
            select(
                sub.c.resolved_agent_id,
                func.count().label("total"),
                func.sum(sub.c.is_confirmed).label("confirmed"),
            )
            .where(sub.c.resolved_agent_id.is_not(None))
            .group_by(sub.c.resolved_agent_id)
            .order_by(func.count().desc())
            .limit(limit)
        )
        rows = self.db.execute(stmt).all()
        return [
            {
                "agent_id": r.resolved_agent_id,
                "total": int(r.total),
                "confirmed": int(r.confirmed or 0),
            }
            for r in rows
        ]

    def crop_frequency(
        self, user: CurrentUser, *, limit: int = 8, include_demo: bool = False
    ) -> list[dict[str, Any]]:
        """Most frequently affected crops."""
        base = self._scoped(select(Observation), user)
        if not include_demo:
            base = base.where(Observation.source_type != "DEMO_SIMULATION")
        sub = base.subquery()
        stmt = (
            select(sub.c.crop_id, func.count().label("total"))
            .where(sub.c.crop_id.is_not(None))
            .group_by(sub.c.crop_id)
            .order_by(func.count().desc())
            .limit(limit)
        )
        rows = self.db.execute(stmt).all()
        return [{"crop_id": r.crop_id, "total": int(r.total)} for r in rows]

    def risk_distribution(self, user: CurrentUser, *, include_demo: bool = False) -> dict[str, int]:
        """Count of observations at each latest risk level."""
        base = self._scoped(select(Observation), user)
        if not include_demo:
            base = base.where(Observation.source_type != "DEMO_SIMULATION")
        sub = base.add_columns(self._latest_risk_level_subquery().label("risk_level")).subquery()
        stmt = (
            select(sub.c.risk_level, func.count().label("total"))
            .where(sub.c.risk_level.is_not(None))
            .group_by(sub.c.risk_level)
        )
        result = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
        for r in self.db.execute(stmt).all():
            result[r.risk_level] = int(r.total)
        return result

    def confirmed_vs_predicted(
        self, user: CurrentUser, *, include_demo: bool = False
    ) -> dict[str, int]:
        """Confirmed diagnoses vs observations that only ever got an AI prediction."""
        base = self._scoped(select(Observation), user)
        if not include_demo:
            base = base.where(Observation.source_type != "DEMO_SIMULATION")

        def _count(stmt: Select) -> int:
            return int(
                self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
            )

        confirmed = _count(base.where(Observation.final_agent_id.is_not(None)))
        ai_only = _count(
            base.where(
                Observation.final_agent_id.is_(None),
                Observation.id.in_(select(AiPrediction.observation_id)),
            )
        )
        return {"confirmed": confirmed, "ai_predicted_only": ai_only}

    def recent_observations(
        self, user: CurrentUser, *, limit: int = 8, include_demo: bool = False
    ) -> list[Observation]:
        """Most recent observations, demo-filtered like every other dashboard figure.

        Deliberately separate from `list_for_user` (used by the plain observation
        list), which has no demo filter: that endpoint is scoped to the caller's own
        records anyway, so a farmer never sees another account's demo data through it.
        The official dashboard is district-wide, so it must filter explicitly here.
        """
        base = self._scoped(select(Observation), user)
        if not include_demo:
            base = base.where(Observation.source_type != "DEMO_SIMULATION")
        stmt = base.order_by(Observation.observed_at.desc()).limit(limit)
        return list(self.db.execute(stmt).scalars())

    def recently_verified(
        self, user: CurrentUser, *, limit: int = 8, include_demo: bool = False
    ) -> list[Observation]:
        """Most recent expert decisions (confirm/correct/reject all set `verified_at`)."""
        base = self._scoped(select(Observation), user)
        if not include_demo:
            base = base.where(Observation.source_type != "DEMO_SIMULATION")
        stmt = (
            base.where(Observation.verified_at.is_not(None))
            .order_by(Observation.verified_at.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars())

    def recent_high_risk(
        self, user: CurrentUser, *, limit: int = 8, include_demo: bool = False
    ) -> list[Observation]:
        base = self._scoped(select(Observation), user)
        if not include_demo:
            base = base.where(Observation.source_type != "DEMO_SIMULATION")
        stmt = (
            base.where(self._latest_risk_level_subquery() == "HIGH")
            .order_by(Observation.observed_at.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars())

    # ---- expert review (Phase 5) ----

    def review_queue(
        self, user: CurrentUser, *, limit: int, offset: int
    ) -> tuple[list[Observation], int]:
        """Observations awaiting expert review, most in-need first.

        Priority: a low-confidence AI prediction goes first (closest to the confidence
        gate boundary), then anything with no prediction at all, then oldest first.
        """
        latest_confidence = (
            select(AiPrediction.confidence)
            .where(AiPrediction.observation_id == Observation.id)
            .order_by(AiPrediction.created_at.desc())
            .limit(1)
            .correlate(Observation)
            .scalar_subquery()
        )
        base = self._scoped(select(Observation), user).where(
            Observation.verification_status == "PENDING_REVIEW"
        )
        total = self.db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
        rows = list(
            self.db.execute(
                base.order_by(latest_confidence.asc().nulls_last(), Observation.observed_at.asc())
                .limit(limit)
                .offset(offset)
            ).scalars()
        )
        return rows, int(total)

    def get_field(self, field_id: uuid.UUID) -> Field | None:
        return (
            self.db.execute(select(Field).where(Field.id == field_id, Field.deleted_at.is_(None)))
            .scalars()
            .first()
        )

    # ---- writes ----

    def create(
        self,
        *,
        latitude: float,
        longitude: float,
        observed_at: datetime,
        **values: Any,
    ) -> Observation:
        observation = Observation(
            latitude=Decimal(str(round(latitude, 6))),
            longitude=Decimal(str(round(longitude, 6))),
            geom=func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326),
            observed_at=observed_at,
            status="PROCESSING",
            **values,
        )
        self.db.add(observation)
        self.db.flush()
        return observation
