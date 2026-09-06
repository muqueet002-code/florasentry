"""Deterministic hotspot detection (Phase 4).

PostGIS `ST_ClusterDBSCAN` - not spatial ML, not a prediction. It groups observations
that are close together into numbered clusters; anything not close enough to `radius_m`
other points (fewer than `min_points` neighbours) is left as noise and excluded.

Every threshold here is a parameter, not a hardcoded number - see the `radius_m`,
`min_points` and `window_days` arguments and their config defaults in
`core/config.py` (HOTSPOT_RADIUS_M, HOTSPOT_MIN_OBSERVATIONS, HOTSPOT_WINDOW_DAYS).

A cluster is classified from what the DATA actually shows, never asserted:
  - "Confirmed hotspot"  - every member is expert-confirmed/corrected
  - "Detected cluster"   - a mix of confirmed and unconfirmed observations
  - "Potential hotspot"  - members are all unconfirmed AI predictions

REJECTED observations never contribute to a cluster - an unsupported report is not
evidence of anything. DEMO_SIMULATION observations are excluded by default so a demo
seed can never be read as a real outbreak; `include_demo=True` is opt-in and every
resulting cluster is flagged `includes_demo_data` so the caller can label it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.models.catalog import DiseasePestCatalog
from app.models.observation import Observation
from app.models.prediction import AiPrediction
from app.repositories.observation_repository import ObservationRepository

CONFIRMED_STATUSES = ("CONFIRMED", "CORRECTED")
UNCONFIRMED_STATUSES = ("PREDICTED", "PENDING_REVIEW", "LAB_REFERRED")
EXCLUDED_STATUSES = ("REJECTED",)  # never contributes to a cluster


@dataclass
class Hotspot:
    cluster_id: int
    centroid_lat: float
    centroid_lon: float
    observation_count: int
    confirmed_count: int
    predicted_count: int
    dominant_agent_code: str | None
    dominant_agent_name: str | None
    avg_severity: float | None
    hotspot_type: str  # CONFIRMED | SIGNAL | PREDICTED
    label: str  # human terminology, see module docstring
    includes_demo_data: bool
    observation_ids: list[str] = field(default_factory=list)


def _classify(confirmed: int, total: int) -> tuple[str, str]:
    """(hotspot_type, human label) from the actual member mix - never asserted."""
    if confirmed == total:
        return "CONFIRMED", "Confirmed hotspot"
    if confirmed > 0:
        return "SIGNAL", "Detected cluster"
    return "PREDICTED", "Potential hotspot"


def compute_hotspots(
    db: Session,
    user: CurrentUser,
    *,
    bbox: tuple[float, float, float, float] | None,
    radius_m: int,
    min_points: int,
    window_days: int,
    agent_id: uuid.UUID | None = None,
    crop_id: uuid.UUID | None = None,
    include_demo: bool = False,
    metric_srid: int = 32643,
) -> list[Hotspot]:
    since = datetime.now(UTC) - timedelta(days=window_days)

    stmt: Select = select(
        Observation.id,
        Observation.latitude,
        Observation.longitude,
        Observation.verification_status,
        Observation.final_agent_id,
        Observation.reported_severity,
        Observation.source_type,
        # Positional args: `func.X(**kwargs)` does NOT translate to PostgreSQL's
        # named-parameter call syntax - kwargs are silently dropped, which previously
        # produced ST_ClusterDBSCAN(geom) with no eps/minpoints and a runtime error.
        func.ST_ClusterDBSCAN(
            func.ST_Transform(Observation.geom, metric_srid),
            radius_m,
            min_points,
        )
        .over()
        .label("cluster_id"),
    ).where(
        Observation.deleted_at.is_(None),
        Observation.observed_at >= since,
        Observation.verification_status.notin_(EXCLUDED_STATUSES),
    )
    stmt = ObservationRepository(db).apply_scope(stmt, user)

    if bbox is not None:
        minx, miny, maxx, maxy = bbox
        stmt = stmt.where(
            func.ST_Intersects(Observation.geom, func.ST_MakeEnvelope(minx, miny, maxx, maxy, 4326))
        )
    if crop_id is not None:
        stmt = stmt.where(Observation.crop_id == crop_id)
    if not include_demo:
        stmt = stmt.where(Observation.source_type != "DEMO_SIMULATION")

    rows = db.execute(stmt).all()
    if not rows:
        return []

    # Fill in the predicted agent for rows with no expert-confirmed final_agent_id yet,
    # via one bulk lookup rather than one query per observation.
    unresolved_ids = [r.id for r in rows if r.final_agent_id is None]
    predicted_agent_by_obs: dict[uuid.UUID, uuid.UUID | None] = {}
    if unresolved_ids:
        latest = (
            select(
                AiPrediction.observation_id,
                AiPrediction.predicted_agent_id,
                func.row_number()
                .over(
                    partition_by=AiPrediction.observation_id,
                    order_by=AiPrediction.created_at.desc(),
                )
                .label("rn"),
            )
            .where(AiPrediction.observation_id.in_(unresolved_ids))
            .subquery()
        )
        pred_rows = db.execute(
            select(latest.c.observation_id, latest.c.predicted_agent_id).where(latest.c.rn == 1)
        ).all()
        predicted_agent_by_obs = {r.observation_id: r.predicted_agent_id for r in pred_rows}

    def agent_for(row: object) -> uuid.UUID | None:
        return row.final_agent_id or predicted_agent_by_obs.get(row.id)

    if agent_id is not None:
        rows = [r for r in rows if agent_for(r) == agent_id]
        if not rows:
            return []

    agent_ids = {aid for r in rows if (aid := agent_for(r)) is not None}
    agent_names: dict[uuid.UUID, tuple[str, str]] = {}
    if agent_ids:
        catalog_rows = db.execute(
            select(
                DiseasePestCatalog.id, DiseasePestCatalog.code, DiseasePestCatalog.name_en
            ).where(DiseasePestCatalog.id.in_(agent_ids))
        ).all()
        agent_names = {r.id: (r.code, r.name_en) for r in catalog_rows}

    clusters: dict[int, list] = {}
    for row in rows:
        if row.cluster_id is None:  # noise - not close enough to `min_points` neighbours
            continue
        clusters.setdefault(row.cluster_id, []).append(row)

    hotspots: list[Hotspot] = []
    for cluster_id, members in clusters.items():
        total = len(members)
        confirmed = sum(1 for m in members if m.verification_status in CONFIRMED_STATUSES)
        predicted = total - confirmed

        agent_counts: dict[uuid.UUID, int] = {}
        for m in members:
            aid = agent_for(m)
            if aid is not None:
                agent_counts[aid] = agent_counts.get(aid, 0) + 1
        dominant_agent_id = (
            max(agent_counts, key=lambda k: agent_counts[k]) if agent_counts else None
        )
        code, name = (
            agent_names.get(dominant_agent_id, (None, None)) if dominant_agent_id else (None, None)
        )

        severities = [m.reported_severity for m in members if m.reported_severity is not None]
        avg_severity = round(sum(severities) / len(severities), 2) if severities else None

        hotspot_type, label = _classify(confirmed, total)
        centroid_lat = sum(float(m.latitude) for m in members) / total
        centroid_lon = sum(float(m.longitude) for m in members) / total

        hotspots.append(
            Hotspot(
                cluster_id=cluster_id,
                centroid_lat=round(centroid_lat, 6),
                centroid_lon=round(centroid_lon, 6),
                observation_count=total,
                confirmed_count=confirmed,
                predicted_count=predicted,
                dominant_agent_code=code,
                dominant_agent_name=name,
                avg_severity=avg_severity,
                hotspot_type=hotspot_type,
                label=label,
                includes_demo_data=any(m.source_type == "DEMO_SIMULATION" for m in members),
                observation_ids=[str(m.id) for m in members],
            )
        )

    # Largest / most significant clusters first.
    hotspots.sort(key=lambda h: (h.confirmed_count, h.observation_count), reverse=True)
    return hotspots
