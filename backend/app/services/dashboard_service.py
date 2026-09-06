"""Official/extension dashboard aggregation (Phase 8).

Nothing here computes anything new: every figure is a straight read of data already
produced by the observation, AI, risk, GIS/hotspot and follow-up modules (Phases 1-7).
Scoping is identical to every other observation-bearing endpoint -
`ObservationRepository`/`FollowupRepository` apply the same role/district rule the map
and review queue already use, so an OFFICIAL sees only their own district here too.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.config import settings
from app.gis.hotspots import compute_hotspots
from app.models.catalog import Crop, DiseasePestCatalog
from app.repositories.followup_repository import FollowupRepository
from app.repositories.observation_repository import ObservationRepository

# A follow-up needing an official's/expert's attention: the farmer reported things
# got worse, or explicitly asked for expert review.
ATTENTION_OUTCOMES = ("WORSENED", "NEEDS_EXPERT_REVIEW")


def _obs_summary(observation: Any) -> dict[str, Any]:
    return {
        "id": str(observation.id),
        "observed_at": observation.observed_at.isoformat(),
        "verification_status": observation.verification_status,
        "source_type": observation.source_type,
        "crop_id": str(observation.crop_id) if observation.crop_id else None,
    }


def _followup_summary(followup: Any) -> dict[str, Any]:
    return {
        "id": str(followup.id),
        "parent_observation_id": str(followup.parent_observation_id),
        "outcome": followup.outcome,
        "status": followup.status,
        "submitted_at": followup.submitted_at.isoformat() if followup.submitted_at else None,
        "notes": followup.notes,
    }


class DashboardService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.observations = ObservationRepository(db)
        self.followups = FollowupRepository(db)

    def official_overview(self, user: CurrentUser, *, include_demo: bool = False) -> dict[str, Any]:
        stats = self.observations.dashboard_stats(user, include_demo=include_demo)

        hotspots = compute_hotspots(
            self.db,
            user,
            bbox=settings.operating_bbox,
            radius_m=settings.HOTSPOT_RADIUS_M,
            min_points=settings.HOTSPOT_MIN_OBSERVATIONS,
            window_days=settings.HOTSPOT_WINDOW_DAYS,
            include_demo=include_demo,
            metric_srid=settings.GIS_METRIC_SRID,
        )

        # Follow-ups worth an official's/expert's attention (Part D of Phase 7,
        # surfaced here rather than a second dashboard).
        attention_rows: list[Any] = []
        attention_total = 0
        for outcome in ATTENTION_OUTCOMES:
            rows, total = self.followups.list_for_user(
                user, outcome=outcome, status="SUBMITTED", include_demo=include_demo, limit=10
            )
            attention_total += total
            attention_rows.extend(rows)
        attention_rows.sort(key=lambda f: f.submitted_at or f.scheduled_for, reverse=True)

        overview = {
            **stats,
            "active_hotspots": len(hotspots),
            "followups_requiring_attention": attention_total,
        }

        # ---- disease / pest summary ----
        agent_rows = self.observations.agent_frequency(user, include_demo=include_demo)
        agent_ids = {r["agent_id"] for r in agent_rows}
        agents = (
            {
                a.id: a
                for a in self.db.query(DiseasePestCatalog).filter(
                    DiseasePestCatalog.id.in_(agent_ids)
                )
            }
            if agent_ids
            else {}
        )
        top_threats = [
            {
                "agent_id": str(r["agent_id"]),
                "agent_code": agents[r["agent_id"]].code if r["agent_id"] in agents else None,
                "agent_name": agents[r["agent_id"]].name_en if r["agent_id"] in agents else None,
                "kind": agents[r["agent_id"]].kind if r["agent_id"] in agents else None,
                "total_observations": r["total"],
                "confirmed_observations": r["confirmed"],
            }
            for r in agent_rows
        ]

        crop_rows = self.observations.crop_frequency(user, include_demo=include_demo)
        crop_ids = {r["crop_id"] for r in crop_rows}
        crops = (
            {c.id: c for c in self.db.query(Crop).filter(Crop.id.in_(crop_ids))} if crop_ids else {}
        )
        affected_crops = [
            {
                "crop_id": str(r["crop_id"]),
                "crop_code": crops[r["crop_id"]].code if r["crop_id"] in crops else None,
                "crop_name": crops[r["crop_id"]].name_en if r["crop_id"] in crops else None,
                "total_observations": r["total"],
            }
            for r in crop_rows
        ]

        disease_pest_summary = {
            "top_threats": top_threats,
            "affected_crops": affected_crops,
            "risk_distribution": self.observations.risk_distribution(
                user, include_demo=include_demo
            ),
            "diagnosis_basis": self.observations.confirmed_vs_predicted(
                user, include_demo=include_demo
            ),
        }

        # ---- priority areas: the existing hotspot ranking (confirmed_count then
        # observation_count, see `compute_hotspots`), relabelled for this view. No
        # new scoring - a hotspot IS a priority area here. ----
        priority_areas = [
            {
                "cluster_id": h.cluster_id,
                "label": h.label,
                "hotspot_type": h.hotspot_type,
                "centroid": {"latitude": h.centroid_lat, "longitude": h.centroid_lon},
                "observation_count": h.observation_count,
                "confirmed_count": h.confirmed_count,
                "dominant_agent_code": h.dominant_agent_code,
                "dominant_agent_name": h.dominant_agent_name,
                "avg_severity": h.avg_severity,
                "includes_demo_data": h.includes_demo_data,
                "disclaimer_key": "hotspot.prototype_disclaimer",
            }
            for h in hotspots[:10]
        ]

        # ---- recent activity ----
        recent_observations = self.observations.recent_observations(
            user, limit=8, include_demo=include_demo
        )
        recent_validations = self.observations.recently_verified(
            user, limit=8, include_demo=include_demo
        )
        recent_high_risk = self.observations.recent_high_risk(
            user, limit=8, include_demo=include_demo
        )

        recent_activity = {
            "observations": [_obs_summary(o) for o in recent_observations],
            "expert_validations": [_obs_summary(o) for o in recent_validations],
            "high_risk_cases": [_obs_summary(o) for o in recent_high_risk],
            "worsening_followups": [_followup_summary(f) for f in attention_rows[:8]],
        }

        # Reflects whether any demo row actually made it into this response - not
        # just whether the caller asked for it - so the banner never claims "demo
        # data included" for a result that happens to contain none, and never omits
        # it when a hotspot (computed independently) pulled some in.
        includes_demo_data = any(
            o.source_type == "DEMO_SIMULATION"
            for o in (*recent_observations, *recent_validations, *recent_high_risk)
        ) or any(h.includes_demo_data for h in hotspots)

        return {
            "overview": overview,
            "disease_pest_summary": disease_pest_summary,
            "priority_areas": priority_areas,
            "recent_activity": recent_activity,
            "includes_demo_data": includes_demo_data,
            "disclaimer_key": "dashboard.prototype_disclaimer",
        }
