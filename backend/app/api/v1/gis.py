"""GIS map and hotspot endpoints (Phase 4).

Every observation-returning endpoint here is bounded - by bbox, by radius, or by a
row cap (`GIS_MAX_FEATURES`) - so a map view can never trigger an unbounded scan.
Results are GeoJSON, and every feature's `properties` always carries `source_type` and
`verification_status`: a map point without provenance must never be renderable.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_current_user, get_db, require_permission
from app.core.config import settings
from app.core.errors import ValidationError
from app.core.rbac import Permission
from app.core.responses import success
from app.gis.hotspots import compute_hotspots
from app.models.catalog import Crop, DiseasePestCatalog
from app.models.observation import Observation
from app.repositories.observation_repository import ObservationRepository

router = APIRouter(tags=["gis"])


def _parse_bbox(bbox: str | None) -> tuple[float, float, float, float]:
    """`minx,miny,maxx,maxy`. Falls back to the configured operating area rather than
    refusing the request outright - every map view is bounded either way."""
    if bbox is None:
        return settings.operating_bbox
    parts = bbox.split(",")
    if len(parts) != 4:
        raise ValidationError(
            "bbox must be 'minx,miny,maxx,maxy'.",
            code="BBOX_INVALID",
            message_key="errors.bbox_invalid",
        )
    try:
        minx, miny, maxx, maxy = (float(p) for p in parts)
    except ValueError as exc:
        raise ValidationError(
            "bbox values must be numeric.",
            code="BBOX_INVALID",
            message_key="errors.bbox_invalid",
        ) from exc
    if not (minx < maxx and miny < maxy):
        raise ValidationError(
            "bbox must satisfy minx<maxx and miny<maxy.",
            code="BBOX_INVALID",
            message_key="errors.bbox_invalid",
        )
    return minx, miny, maxx, maxy


def _agent_label(
    db: Session, observation: Observation, prediction_agent_id: uuid.UUID | None
) -> tuple[str | None, str | None, str]:
    """(code, name, match_basis) - distinguishes a confirmed diagnosis from a
    still-unconfirmed AI prediction, as every GIS layer must (TRD 9.4-F)."""
    if observation.final_agent_id is not None:
        agent = db.get(DiseasePestCatalog, observation.final_agent_id)
        return (agent.code, agent.name_en, "CONFIRMED_AGENT") if agent else (None, None, "NONE")
    if prediction_agent_id is not None:
        agent = db.get(DiseasePestCatalog, prediction_agent_id)
        return (agent.code, agent.name_en, "PREDICTED_AGENT") if agent else (None, None, "NONE")
    return None, None, "NONE"


def _feature(
    db: Session,
    observation: Observation,
    *,
    prediction: Any | None,
    risk: Any | None,
    crop_by_id: dict[uuid.UUID, Crop],
) -> dict[str, Any]:
    crop = crop_by_id.get(observation.crop_id) if observation.crop_id else None
    agent_code, agent_name, match_basis = _agent_label(
        db, observation, prediction.predicted_agent_id if prediction else None
    )
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [float(observation.longitude), float(observation.latitude)],
        },
        "properties": {
            "id": str(observation.id),
            # Provenance is never optional on a map feature.
            "source_type": observation.source_type,
            "verification_status": observation.verification_status,
            "crop_code": crop.code if crop else None,
            "crop_name": crop.name_en if crop else None,
            "agent_code": agent_code,
            "agent_name": agent_name,
            "match_basis": match_basis,
            "confidence": float(prediction.confidence) if prediction else None,
            "risk_level": risk.risk_level if risk else None,
            "risk_score": float(risk.risk_score) if risk else None,
            "reported_severity": observation.reported_severity,
            "observed_at": observation.observed_at.isoformat(),
        },
    }


def _feature_collection(db: Session, observations: list[Observation]) -> dict[str, Any]:
    repo = ObservationRepository(db)
    ids = [o.id for o in observations]
    predictions = repo.latest_predictions_bulk(ids)
    risks = repo.latest_risk_bulk(ids)
    crop_ids = {o.crop_id for o in observations if o.crop_id is not None}
    crops = (
        {c.id: c for c in db.query(Crop).filter(Crop.id.in_(crop_ids)).all()} if crop_ids else {}
    )

    return {
        "type": "FeatureCollection",
        "features": [
            _feature(
                db, o, prediction=predictions.get(o.id), risk=risks.get(o.id), crop_by_id=crops
            )
            for o in observations
        ],
    }


@router.get("/gis/observations", summary="Observation points for the map")
def gis_observations(
    bbox: str | None = Query(default=None, description="minx,miny,maxx,maxy"),
    crop_id: uuid.UUID | None = None,
    agent_id: uuid.UUID | None = None,
    verification_status: str | None = Query(
        default=None,
        pattern="^(PREDICTED|PENDING_REVIEW|CONFIRMED|CORRECTED|REJECTED|LAB_REFERRED)$",
    ),
    risk_level: str | None = Query(default=None, pattern="^(LOW|MEDIUM|HIGH)$"),
    date_from: datetime | None = Query(default=None, alias="from"),
    date_to: datetime | None = Query(default=None, alias="to"),
    include_demo: bool = Query(default=False),
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    parsed_bbox = _parse_bbox(bbox)
    repo = ObservationRepository(db)
    observations = repo.query_bbox(
        current,
        bbox=parsed_bbox,
        crop_id=crop_id,
        agent_id=agent_id,
        verification_status=verification_status,
        risk_level=risk_level,
        date_from=date_from,
        date_to=date_to,
        include_demo=include_demo,
        limit=settings.GIS_MAX_FEATURES,
    )
    collection = _feature_collection(db, observations)
    return success(
        collection,
        truncated=len(observations) >= settings.GIS_MAX_FEATURES,
        filters_applied={
            "bbox": list(parsed_bbox),
            "crop_id": str(crop_id) if crop_id else None,
            "agent_id": str(agent_id) if agent_id else None,
            "verification_status": verification_status,
            "risk_level": risk_level,
            "include_demo": include_demo,
        },
    )


@router.get("/gis/nearby", summary="Observations within a radius of a point")
def gis_nearby(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius_m: int = Query(default=2000, gt=0, le=50000),
    window_days: int | None = Query(default=None, gt=0),
    include_demo: bool = Query(default=False),
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    repo = ObservationRepository(db)
    observations = repo.query_nearby(
        current,
        latitude=lat,
        longitude=lon,
        radius_m=radius_m,
        window_days=window_days,
        include_demo=include_demo,
    )
    return success(_feature_collection(db, observations))


@router.get("/gis/hotspots", summary="Detected observation clusters")
def gis_hotspots(
    bbox: str | None = Query(default=None, description="minx,miny,maxx,maxy"),
    radius_m: int | None = Query(default=None, gt=0, le=50000),
    min_points: int | None = Query(default=None, ge=2, le=50),
    window_days: int | None = Query(default=None, gt=0, le=365),
    agent_id: uuid.UUID | None = None,
    crop_id: uuid.UUID | None = None,
    include_demo: bool = Query(default=False),
    current: CurrentUser = Depends(require_permission(Permission.VIEW_HOTSPOTS)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Deterministic PostGIS clustering (ST_ClusterDBSCAN) - not spatial ML, not a
    forecast. See app/gis/hotspots.py for the classification rule and its limits."""
    parsed_bbox = _parse_bbox(bbox)
    effective_radius = radius_m or settings.HOTSPOT_RADIUS_M
    effective_min_points = min_points or settings.HOTSPOT_MIN_OBSERVATIONS
    effective_window = window_days or settings.HOTSPOT_WINDOW_DAYS

    hotspots = compute_hotspots(
        db,
        current,
        bbox=parsed_bbox,
        radius_m=effective_radius,
        min_points=effective_min_points,
        window_days=effective_window,
        agent_id=agent_id,
        crop_id=crop_id,
        include_demo=include_demo,
        metric_srid=settings.GIS_METRIC_SRID,
    )

    return success(
        [
            {
                "cluster_id": h.cluster_id,
                "hotspot_type": h.hotspot_type,
                "label": h.label,
                "centroid": {"latitude": h.centroid_lat, "longitude": h.centroid_lon},
                "radius_m": effective_radius,
                "observation_count": h.observation_count,
                "confirmed_count": h.confirmed_count,
                "predicted_count": h.predicted_count,
                "dominant_agent_code": h.dominant_agent_code,
                "dominant_agent_name": h.dominant_agent_name,
                "avg_severity": h.avg_severity,
                "includes_demo_data": h.includes_demo_data,
                "observation_ids": h.observation_ids,
                # Prototype heuristic, not a validated outbreak-detection claim.
                "disclaimer_key": "hotspot.prototype_disclaimer",
            }
            for h in hotspots
        ],
        filters_applied={
            "bbox": list(parsed_bbox),
            "radius_m": effective_radius,
            "min_points": effective_min_points,
            "window_days": effective_window,
            "agent_id": str(agent_id) if agent_id else None,
            "crop_id": str(crop_id) if crop_id else None,
            "include_demo": include_demo,
        },
    )
