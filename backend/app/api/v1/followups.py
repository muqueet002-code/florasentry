"""Follow-up endpoints (Phase 7).

Reuses `_observation_out` (observations.py) so a submitted follow-up's linked
observation renders exactly like any other observation - same image handling, same
prediction/risk/verification-status shape, same provenance rules.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_current_user, get_db, require_permission
from app.api.v1.observations import _observation_out
from app.core.errors import ValidationError
from app.core.rbac import Permission
from app.core.responses import paginated, success
from app.models.followup import Followup
from app.models.observation import Observation
from app.repositories.followup_repository import FollowupRepository
from app.repositories.observation_repository import ObservationRepository
from app.schemas.followup import FollowupCreate, FollowupSubmit
from app.services.followup_service import FollowupService

router = APIRouter(tags=["followups"])


def _followup_out(followup: Followup, db: Session) -> dict[str, Any]:
    linked_observation = None
    if followup.followup_observation_id:
        repo = ObservationRepository(db)
        obs = db.get(Observation, followup.followup_observation_id)
        if obs is not None:
            linked_observation = _observation_out(
                obs,
                image=repo.primary_image(obs.id),
                prediction=repo.latest_prediction(obs.id),
                risk=repo.latest_risk(obs.id),
            )

    is_due = followup.status == "SCHEDULED" and followup.scheduled_for <= datetime.now(UTC)

    return {
        "id": str(followup.id),
        "parent_observation_id": str(followup.parent_observation_id),
        "followup_observation_id": (
            str(followup.followup_observation_id) if followup.followup_observation_id else None
        ),
        "scheduled_for": followup.scheduled_for.isoformat(),
        "status": followup.status,
        "is_due": is_due,
        "outcome": followup.outcome,
        "notes": followup.notes,
        "submitted_at": followup.submitted_at.isoformat() if followup.submitted_at else None,
        "created_at": followup.created_at.isoformat(),
        "linked_observation": linked_observation,
    }


@router.post(
    "/followups",
    status_code=status.HTTP_201_CREATED,
    summary="Schedule a follow-up for an observation",
)
def create_followup(
    payload: FollowupCreate,
    current: CurrentUser = Depends(require_permission(Permission.SUBMIT_FOLLOWUP)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    followup = FollowupService(db).create(
        user=current,
        observation_id=payload.observation_id,
        scheduled_for=payload.scheduled_for,
    )
    return success(_followup_out(followup, db))


@router.get("/followups", summary="List follow-ups visible to the caller")
def list_followups(
    observation_id: uuid.UUID | None = Query(default=None),
    outcome: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    include_demo: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """`outcome=WORSENED` (or `NEEDS_EXPERT_REVIEW`) lets an expert triage without a
    separate dashboard - the existing role scope already limits results to their
    district, exactly as `/reviews/queue` does. `include_demo` defaults to false, same
    as every GIS/dashboard listing, so simulated data never mixes into a real triage
    list unless explicitly requested."""
    rows, total = FollowupRepository(db).list_for_user(
        current,
        observation_id=observation_id,
        outcome=outcome,
        include_demo=include_demo,
        status=status_filter,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return paginated(
        [_followup_out(f, db) for f in rows], page=page, page_size=page_size, total_items=total
    )


@router.get("/followups/{followup_id}", summary="Follow-up detail")
def get_followup(
    followup_id: uuid.UUID,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    followup = FollowupService(db).get_for_user(followup_id, current)
    return success(_followup_out(followup, db))


@router.post("/followups/{followup_id}/submit", summary="Submit a due follow-up")
def submit_followup(
    followup_id: uuid.UUID,
    payload: str = Form(..., description="JSON body matching FollowupSubmit"),
    image: UploadFile | None = File(default=None),
    current: CurrentUser = Depends(require_permission(Permission.SUBMIT_FOLLOWUP)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        parsed = FollowupSubmit.model_validate(json.loads(payload))
    except json.JSONDecodeError as exc:
        raise ValidationError(
            "The `payload` part is not valid JSON.",
            details=[{"field": "payload", "issue": "invalid_json"}],
        ) from exc
    except PydanticValidationError as exc:
        raise ValidationError(
            "Follow-up payload failed validation.",
            details=[
                {
                    "field": ".".join(str(p) for p in err.get("loc", [])),
                    "issue": err.get("type", "invalid"),
                    "message": err.get("msg", ""),
                }
                for err in exc.errors()
            ],
        ) from exc

    image_bytes = image.file.read() if image is not None else None
    followup, outcome = FollowupService(db).submit(
        followup_id=followup_id,
        user=current,
        outcome=parsed.outcome,
        notes=parsed.notes,
        image_bytes=image_bytes,
        declared_mime=image.content_type if image else None,
    )
    body = _followup_out(followup, db)
    return success(body, warnings=outcome.warnings or None)
