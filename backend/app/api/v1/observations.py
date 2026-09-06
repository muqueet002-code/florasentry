"""Observation, image and AI endpoints (Phase 2 + 3)."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from app.ai import inference_service
from app.api.deps import CurrentUser, get_current_user, get_db, require_permission
from app.core.errors import NotFoundError, OwnershipError, ValidationError
from app.core.rbac import Permission
from app.core.responses import paginated, success
from app.integrations.storage import get_storage
from app.models.observation import Observation, ObservationImage
from app.models.prediction import AiPrediction
from app.models.risk import RiskAssessment
from app.repositories.observation_repository import ObservationRepository
from app.schemas.observation import ObservationCreate
from app.services.observation_service import ObservationService
from app.services.weather_service import WeatherSnapshot

router = APIRouter(tags=["observations"])


# ---- serialisation -----------------------------------------------------------


def _image_out(image: ObservationImage | None) -> dict[str, Any] | None:
    if image is None:
        return None
    return {
        "id": str(image.id),
        # Images are served only through an authorising endpoint, never as a
        # public storage path.
        "url": f"/api/v1/images/{image.id}",
        "thumbnail_url": f"/api/v1/images/{image.id}?variant=thumbnail",
        "width_px": image.width_px,
        "height_px": image.height_px,
        "quality_flags": image.quality_flags,
    }


def _prediction_out(prediction: AiPrediction | None) -> dict[str, Any] | None:
    if prediction is None:
        return None
    return {
        "predicted_class": prediction.predicted_class,
        "agent_id": str(prediction.predicted_agent_id) if prediction.predicted_agent_id else None,
        "confidence": float(prediction.confidence),
        "is_low_confidence": prediction.is_low_confidence,
        "top_k": prediction.top_k,
        "severity_estimate": (
            float(prediction.severity_estimate)
            if prediction.severity_estimate is not None
            else None
        ),
        "model_version": prediction.model_version,
        "inference_ms": prediction.inference_ms,
        "runtime_device": prediction.runtime_device,
        "created_at": prediction.created_at.isoformat(),
    }


def _weather_out(snapshot: WeatherSnapshot | None) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    reading = snapshot.reading
    return {
        "available": snapshot.available,
        "is_stale": snapshot.is_stale,
        "provider": snapshot.provider,
        "observed_at": reading.observed_at.isoformat() if reading else None,
        "temperature_c": reading.temperature_c if reading else None,
        "humidity_pct": reading.humidity_pct if reading else None,
        "rainfall_mm": reading.rainfall_mm if reading else None,
        "wind_speed_ms": reading.wind_speed_ms if reading else None,
        "pressure_hpa": reading.pressure_hpa if reading else None,
        "fetched_at": snapshot.fetched_at.isoformat() if snapshot.fetched_at else None,
        "cache_hit": snapshot.cache_hit,
        "age_hours": round(snapshot.age_hours, 2) if snapshot.age_hours is not None else None,
        "unavailable_reason": snapshot.unavailable_reason,
    }


def _risk_out(risk: RiskAssessment | None) -> dict[str, Any] | None:
    if risk is None:
        return None
    return {
        "risk_score": float(risk.risk_score),
        "risk_level": risk.risk_level,
        "forecast_period_start": risk.forecast_period_start.isoformat(),
        "forecast_period_end": risk.forecast_period_end.isoformat(),
        "contributing_factors": risk.contributing_factors,
        "missing_factors": risk.missing_factors or [],
        "explanation_key": risk.explanation_key,
        "explanation_params": risk.explanation_params,
        "uncertainty": float(risk.uncertainty) if risk.uncertainty is not None else None,
        "method": risk.method,
        "ruleset_version": risk.ruleset_version,
        "weather_is_stale": risk.weather_is_stale,
        "disclaimer_key": "risk.prototype_disclaimer",
        "computed_at": risk.computed_at.isoformat(),
    }


def _observation_out(
    observation: Observation,
    *,
    image: ObservationImage | None = None,
    prediction: AiPrediction | None = None,
    weather: WeatherSnapshot | None = None,
    risk: RiskAssessment | None = None,
) -> dict[str, Any]:
    return {
        "id": str(observation.id),
        "status": observation.status,
        # Truth state, always emitted alongside the prediction.
        "verification_status": observation.verification_status,
        "observation_type": observation.observation_type,
        "latitude": float(observation.latitude),
        "longitude": float(observation.longitude),
        "gps_accuracy_m": (
            float(observation.gps_accuracy_m) if observation.gps_accuracy_m is not None else None
        ),
        "observed_at": observation.observed_at.isoformat(),
        "reported_severity": observation.reported_severity,
        "notes": observation.notes,
        "field_id": str(observation.field_id) if observation.field_id else None,
        "crop_id": str(observation.crop_id) if observation.crop_id else None,
        "variety_id": str(observation.variety_id) if observation.variety_id else None,
        "growth_stage_id": (
            str(observation.growth_stage_id) if observation.growth_stage_id else None
        ),
        # NULL unless an expert confirmed or corrected - enforced by a DB constraint.
        "final_agent_id": str(observation.final_agent_id) if observation.final_agent_id else None,
        "image": _image_out(image),
        "prediction": _prediction_out(prediction),
        "weather": _weather_out(weather),
        "risk": _risk_out(risk),
        "processing_errors": observation.processing_errors,
        "provenance": {
            "source_type": observation.source_type,
            "created_by": str(observation.reported_by),
            "created_at": observation.created_at.isoformat(),
            "verified_by": str(observation.verified_by) if observation.verified_by else None,
            "verified_at": (
                observation.verified_at.isoformat() if observation.verified_at else None
            ),
            "model_version": prediction.model_version if prediction else None,
        },
    }


# ---- endpoints ---------------------------------------------------------------


@router.post(
    "/observations",
    status_code=status.HTTP_201_CREATED,
    summary="Create an observation and run the AI + risk pipeline",
)
def create_observation(
    payload: str = Form(..., description="JSON body matching ObservationCreate"),
    image: UploadFile | None = File(default=None),
    current: CurrentUser = Depends(require_permission(Permission.CREATE_OBSERVATION)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Multipart: `payload` (JSON) plus an optional `image` file.

    Returns 201 with the combined result. Enrichment failures appear as `warnings`
    plus `processing_errors` - they never fail the request or lose the observation.
    """
    try:
        parsed = ObservationCreate.model_validate(json.loads(payload))
    except json.JSONDecodeError as exc:
        raise ValidationError(
            "The `payload` part is not valid JSON.",
            details=[{"field": "payload", "issue": "invalid_json"}],
        ) from exc
    except PydanticValidationError as exc:
        raise ValidationError(
            "Observation payload failed validation.",
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

    service = ObservationService(db)
    outcome = service.create_with_image(
        user_id=current.id,
        farmer_id=current.farmer_id,
        payload=parsed,
        image_bytes=image_bytes,
        declared_mime=image.content_type if image else None,
    )

    weather = outcome.context.weather if outcome.context else None
    body = _observation_out(
        outcome.observation,
        image=outcome.image,
        prediction=outcome.prediction,
        weather=weather,
        risk=outcome.risk,
    )
    return success(body, warnings=outcome.warnings or None)


@router.get("/observations", summary="List observations visible to the caller")
def list_observations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    repo = ObservationRepository(db)
    rows, total = repo.list_for_user(current, limit=page_size, offset=(page - 1) * page_size)
    items = [
        _observation_out(
            row,
            image=repo.primary_image(row.id),
            prediction=repo.latest_prediction(row.id),
            risk=repo.latest_risk(row.id),
        )
        for row in rows
    ]
    return paginated(items, page=page, page_size=page_size, total_items=total)


@router.get("/observations/{observation_id}", summary="Observation detail")
def get_observation(
    observation_id: uuid.UUID,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    service = ObservationService(db)
    outcome = service.get_detail(observation_id, current)
    # Weather is read from cache for the detail view; it does not re-trigger the
    # pipeline, so opening a record cannot cost a provider call per view.
    weather = service.refresh_weather_snapshot(outcome.observation)
    warnings: list[dict[str, Any]] = []
    if not weather.available:
        warnings.append(
            {"code": "WEATHER_UNAVAILABLE", "message_key": "warnings.weather_unavailable"}
        )
    elif weather.is_stale:
        warnings.append({"code": "WEATHER_STALE", "message_key": "warnings.weather_stale"})

    return success(
        _observation_out(
            outcome.observation,
            image=outcome.image,
            prediction=outcome.prediction,
            weather=weather,
            risk=outcome.risk,
        ),
        warnings=warnings or None,
    )


@router.get("/observations/{observation_id}/status", summary="Lightweight status poll")
def get_observation_status(
    observation_id: uuid.UUID,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    observation = ObservationRepository(db).get_for_user(observation_id, current)
    if observation is None:
        raise NotFoundError("Observation")
    return success(
        {
            "id": str(observation.id),
            "status": observation.status,
            "verification_status": observation.verification_status,
            "processing_errors": observation.processing_errors,
        }
    )


@router.get("/images/{image_id}", summary="Fetch an observation image")
def get_image(
    image_id: uuid.UUID,
    variant: str = Query(default="original", pattern="^(original|thumbnail)$"),
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Authorised image read. Storage keys are never publicly addressable."""
    repo = ObservationRepository(db)
    image = repo.get_image(image_id)
    if image is None:
        raise NotFoundError("Image")

    # Re-check access through the observation's own scoping rule.
    if repo.get_for_user(image.observation_id, current) is None:
        raise OwnershipError()

    key = (
        image.thumbnail_key if variant == "thumbnail" and image.thumbnail_key else image.storage_key
    )
    data = get_storage().get(key)
    return Response(content=data, media_type=image.mime_type)


@router.get("/ai/models/active", summary="Active model status and thresholds")
def active_model(
    _: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Reports AI_MODEL_UNAVAILABLE honestly when no usable model is registered."""
    return success(inference_service.model_status(db))


@router.post("/ai/analyze", summary="Stateless inference (no observation created)")
def analyze(
    image: UploadFile = File(...),
    _: CurrentUser = Depends(require_permission(Permission.RUN_AI_ANALYZE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """For expert/testing use. Raises rather than returning a fabricated result."""
    from app.ai.interface import InferenceFailedError
    from app.ai.preprocessing import validate_and_prepare
    from app.core.errors import ExternalServiceError

    prepared = validate_and_prepare(image.file.read(), image.content_type)

    try:
        gated = inference_service.run_inference(db, prepared.data)
    except inference_service.AiUnavailable as exc:
        raise ExternalServiceError(
            f"No usable AI model: {exc.reason}",
            code="AI_MODEL_UNAVAILABLE",
            message_key="errors.ai_model_unavailable",
        ) from exc
    except InferenceFailedError as exc:
        raise ExternalServiceError(
            "Inference failed.",
            code="AI_INFERENCE_FAILED",
            message_key="errors.ai_inference_failed",
            details=[{"reason": str(exc)}],
        ) from exc

    return success(
        {
            "predicted_class": gated.result.predicted_class,
            "confidence": round(gated.result.confidence, 4),
            "is_low_confidence": gated.is_low_confidence,
            "top_k": inference_service.top_k_payload(gated.result.top_k),
            "model_version": gated.model_version,
            "inference_ms": gated.result.inference_ms,
            # Mandatory: this endpoint returns a prediction, never a diagnosis.
            "disclaimer_key": "ai.prediction_not_diagnosis",
        }
    )
