"""Expert review endpoints (Phase 5).

Reuses the same observation serialiser as `observations.py` so a reviewer sees exactly
the same shape a farmer does (image, AI prediction, confidence, risk) plus the review
outcome. Nothing here is a parallel data model.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_db, require_permission
from app.api.v1.observations import _observation_out
from app.core.rbac import Permission
from app.core.responses import paginated, success
from app.repositories.observation_repository import ObservationRepository
from app.schemas.review import ReviewDecision
from app.services.review_service import ReviewService

router = APIRouter(tags=["expert-review"])


@router.get("/reviews/queue", summary="Observations awaiting expert review")
def review_queue(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current: CurrentUser = Depends(require_permission(Permission.VIEW_REVIEW_QUEUE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Priority-ordered: low-confidence predictions first, then oldest first."""
    service = ReviewService(db)
    repo = ObservationRepository(db)
    rows, total = service.queue(current, page=page, page_size=page_size)

    obs_ids = [r.id for r in rows]
    predictions = repo.latest_predictions_bulk(obs_ids)
    risks = repo.latest_risk_bulk(obs_ids)

    items = [
        _observation_out(
            row,
            image=repo.primary_image(row.id),
            prediction=predictions.get(row.id),
            risk=risks.get(row.id),
        )
        for row in rows
    ]
    return paginated(items, page=page, page_size=page_size, total_items=total)


@router.get("/reviews/{observation_id}", summary="Case detail for review")
def review_detail(
    observation_id: uuid.UUID,
    current: CurrentUser = Depends(require_permission(Permission.VIEW_REVIEW_QUEUE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    service = ReviewService(db)
    repo = ObservationRepository(db)
    observation = service.get_for_review(observation_id, current)

    return success(
        _observation_out(
            observation,
            image=repo.primary_image(observation.id),
            prediction=repo.latest_prediction(observation.id),
            risk=repo.latest_risk(observation.id),
        )
    )


@router.post("/reviews/{observation_id}/decision", summary="Confirm, correct or reject")
def submit_decision(
    observation_id: uuid.UUID,
    payload: ReviewDecision,
    current: CurrentUser = Depends(require_permission(Permission.DECIDE_REVIEW)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Never touches `ai_predictions` - only the observation's own verification
    columns. The prediction that was reviewed remains exactly as the model produced it."""
    service = ReviewService(db)
    repo = ObservationRepository(db)
    observation = service.decide(observation_id, current, payload)

    return success(
        _observation_out(
            observation,
            image=repo.primary_image(observation.id),
            prediction=repo.latest_prediction(observation.id),
            risk=repo.latest_risk(observation.id),
        )
    )
