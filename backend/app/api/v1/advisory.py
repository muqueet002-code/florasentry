"""Advisory endpoint (Phase 6).

Computed on demand from the observation's CURRENT state - never persisted, never
frozen. If an expert corrects a diagnosis after the advisory was first shown, the next
request reflects the correction automatically. This is the same reasoning as
`refresh_weather_snapshot` in observation_service.py: recomputing from current data is
simpler and more correct than caching something that can go stale.

Reuses `_agent_label` (gis.py) and `_localised` (catalog.py) rather than
reimplementing the confirmed-vs-predicted resolution or per-language field lookup.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.advisory.engine import AdvisoryEngine
from app.api.deps import CurrentUser, get_current_user, get_db, get_language
from app.api.v1.catalog import _localised
from app.api.v1.gis import _agent_label
from app.core.errors import NotFoundError
from app.core.responses import success
from app.models.catalog import DiseasePestCatalog
from app.repositories.observation_repository import ObservationRepository

router = APIRouter(tags=["advisory"])

_engine = AdvisoryEngine()


@router.get("/observations/{observation_id}/advisory", summary="IPM-oriented advisory")
def get_advisory(
    observation_id: uuid.UUID,
    lang: str = Depends(get_language),
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    repo = ObservationRepository(db)
    observation = repo.get_for_user(observation_id, current)
    if observation is None:
        raise NotFoundError("Observation")

    prediction = repo.latest_prediction(observation.id)
    risk = repo.latest_risk(observation.id)

    agent_code, agent_name, match_basis = _agent_label(
        db, observation, prediction.predicted_agent_id if prediction else None
    )
    agent_kind: str | None = None
    resolved_agent_id = observation.final_agent_id or (
        prediction.predicted_agent_id if prediction else None
    )
    if resolved_agent_id is not None:
        agent = db.get(DiseasePestCatalog, resolved_agent_id)
        if agent is not None:
            agent_kind = agent.kind
            agent_name = _localised(agent, "name", lang)

    result = _engine.evaluate(
        verification_status=observation.verification_status,
        agent_kind=agent_kind,
        risk_level=risk.risk_level if risk else None,
    )

    return success(
        {
            "observation_id": str(observation.id),
            # Always present alongside the advisory: a client cannot render guidance
            # without also knowing whether it is confirmed, predicted or unreviewed.
            "verification_status": observation.verification_status,
            "tier": result.tier,
            "agent_code": agent_code,
            "agent_name": agent_name,
            "match_basis": match_basis,  # CONFIRMED_AGENT | PREDICTED_AGENT | NONE
            "confidence": float(prediction.confidence) if prediction else None,
            "risk_level": risk.risk_level if risk else None,
            "sections": [{"key": s.key, "params": s.params} for s in result.sections],
            "method": result.method,
            "ruleset_version": result.ruleset_version,
            "disclaimer_key": result.disclaimer_key,
            "language": lang,
        }
    )
