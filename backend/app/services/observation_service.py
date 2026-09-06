"""Observation pipeline (Phase 2 + 3).

    image -> validate -> store -> persist observation
          -> AI -> confidence gate
          -> weather -> context -> risk
          -> return combined result

THE GOVERNING RULE: the observation must survive. Everything after persistence is
enrichment. Enrichment may fail; the farmer's report must not be lost, and the failure
must be visible in `processing_errors` rather than disguised.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.ai import inference_service
from app.ai.interface import InferenceFailedError
from app.ai.preprocessing import ValidatedImage, validate_and_prepare
from app.core.config import settings
from app.core.errors import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.integrations.storage import checksum, get_storage
from app.models.observation import Observation, ObservationImage
from app.models.prediction import AiPrediction
from app.models.risk import RiskAssessment
from app.repositories.observation_repository import ObservationRepository
from app.risk.context import AiSignal, ContextEngine, RiskContext
from app.risk.rule_engine import RiskResult, RiskUnavailableError, RuleBasedRiskEngine
from app.services.audit_service import AuditService
from app.services.weather_service import WeatherService

logger = get_logger(__name__)

ACTION_OBSERVATION_CREATED = "OBSERVATION_CREATED"


@dataclass
class PipelineOutcome:
    """Everything produced for one observation, including what degraded."""

    observation: Observation
    image: ObservationImage | None = None
    prediction: AiPrediction | None = None
    risk: RiskAssessment | None = None
    risk_result: RiskResult | None = None
    context: RiskContext | None = None
    warnings: list[dict[str, Any]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.warnings is None:
            self.warnings = []


class ObservationService:
    def __init__(self, db: Session, weather_service: WeatherService | None = None) -> None:
        self.db = db
        self.repo = ObservationRepository(db)
        self.audit = AuditService(db)
        self.weather = weather_service or WeatherService(db)

    # ---- creation -------------------------------------------------------------

    def create_with_image(
        self,
        *,
        user_id: uuid.UUID,
        farmer_id: uuid.UUID | None,
        payload: Any,
        image_bytes: bytes | None,
        declared_mime: str | None = None,
    ) -> PipelineOutcome:
        self._validate_coordinates(payload.latitude, payload.longitude)
        field = self._resolve_field(payload.field_id, farmer_id)
        self._validate_crop_context(payload.crop_id, payload.variety_id, payload.growth_stage_id)

        # 1. Validate the image BEFORE writing anything, so a bad upload leaves no row.
        prepared: ValidatedImage | None = None
        if payload.observation_type == "IMAGE":
            if not image_bytes:
                raise ValidationError(
                    "An image is required for an image observation.",
                    code="IMAGE_INVALID",
                    message_key="errors.image_required",
                    details=[{"field": "image", "issue": "missing"}],
                )
            prepared = validate_and_prepare(image_bytes, declared_mime)

        # 2. Persist the observation. From here on it survives every downstream failure.
        observation = self.repo.create(
            farmer_id=farmer_id,
            reported_by=user_id,
            field_id=field.id if field else None,
            crop_id=payload.crop_id,
            variety_id=payload.variety_id,
            growth_stage_id=payload.growth_stage_id,
            observation_type=payload.observation_type,
            latitude=payload.latitude,
            longitude=payload.longitude,
            gps_accuracy_m=payload.gps_accuracy_m,
            location_method=payload.location_method,
            observed_at=payload.observed_at or datetime.now(UTC),
            reported_severity=payload.reported_severity,
            notes=payload.notes,
            district_code=field.district_code if field else None,
            # An observation created through the authenticated API is real. Only the
            # demo seeder may write DEMO_SIMULATION.
            source_type="FIELD_OBSERVATION",
        )

        image_row: ObservationImage | None = None
        if prepared is not None:
            image_row = self._store_image(observation, prepared, user_id)

        outcome = PipelineOutcome(observation=observation, image=image_row)

        # 3. Enrichment. Each stage degrades independently.
        self._run_ai(outcome, prepared)
        self._run_risk(outcome)

        self._finalise_status(outcome)
        self.audit.record(
            action=ACTION_OBSERVATION_CREATED,
            entity_type="observation",
            entity_id=observation.id,
            actor_user_id=user_id,
            after_state={
                "status": observation.status,
                "verification_status": observation.verification_status,
                "source_type": observation.source_type,
            },
        )
        return outcome

    # ---- stages ---------------------------------------------------------------

    def _store_image(
        self, observation: Observation, prepared: ValidatedImage, user_id: uuid.UUID
    ) -> ObservationImage:
        image_id = uuid.uuid4()
        prefix = f"observations/{observation.observed_at:%Y/%m}/{observation.id}"
        storage_key = f"{prefix}/{image_id}.jpg"
        thumb_key = f"{prefix}/thumb_{image_id}.jpg"

        storage = get_storage()
        storage.put(storage_key, prepared.data)
        storage.put(thumb_key, prepared.thumbnail)

        row = ObservationImage(
            id=image_id,
            observation_id=observation.id,
            storage_key=storage_key,
            thumbnail_key=thumb_key,
            mime_type=prepared.mime_type,
            size_bytes=len(prepared.data),
            width_px=prepared.width,
            height_px=prepared.height,
            checksum_sha256=checksum(prepared.data),
            exif_latitude=(
                Decimal(str(round(prepared.exif_latitude, 6)))
                if prepared.exif_latitude is not None
                else None
            ),
            exif_longitude=(
                Decimal(str(round(prepared.exif_longitude, 6)))
                if prepared.exif_longitude is not None
                else None
            ),
            quality_flags=prepared.quality_flags,
            is_primary=True,
            uploaded_by=user_id,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def _run_ai(self, outcome: PipelineOutcome, prepared: ValidatedImage | None) -> None:
        """Run inference. Any failure degrades the observation; it never loses it."""
        observation = outcome.observation

        if prepared is None:
            outcome.observation.status = "COMPLETED"
            return

        try:
            gated = inference_service.run_inference(self.db, prepared.data)
        except inference_service.AiUnavailable as exc:
            # No usable model. Route to a human rather than inventing a result.
            self._degrade(
                outcome,
                status="COMPLETED",
                verification_status="PENDING_REVIEW",
                error_key="ai",
                error={"code": "AI_MODEL_UNAVAILABLE", "reason": exc.reason},
                warning={
                    "code": "AI_MODEL_UNAVAILABLE",
                    "message_key": "warnings.ai_model_unavailable",
                    "detail": {"reason": exc.reason},
                },
            )
            return
        except InferenceFailedError as exc:
            self._degrade(
                outcome,
                status="AI_FAILED",
                verification_status="PENDING_REVIEW",
                error_key="ai",
                error={"code": "AI_INFERENCE_FAILED", "reason": str(exc)},
                warning={
                    "code": "AI_INFERENCE_FAILED",
                    "message_key": "warnings.ai_inference_failed",
                    "detail": {"reason": str(exc)},
                },
            )
            return

        result = gated.result
        agent_id = inference_service.resolve_agent_id(self.db, result.predicted_class)

        prediction = AiPrediction(
            observation_id=observation.id,
            image_id=outcome.image.id if outcome.image else None,
            model_version=gated.model_version,
            predicted_agent_id=agent_id,
            predicted_class=result.predicted_class,
            confidence=inference_service.to_decimal(result.confidence),
            top_k=inference_service.top_k_payload(result.top_k),
            severity_estimate=(
                inference_service.to_decimal(result.severity_estimate)
                if result.severity_estimate is not None
                else None
            ),
            is_low_confidence=gated.is_low_confidence,
            inference_ms=result.inference_ms,
            runtime_device=result.runtime_device,
        )
        self.db.add(prediction)
        self.db.flush()

        outcome.prediction = prediction
        # The confidence gate decides the truth state. `final_agent_id` stays NULL:
        # only an expert may set it (enforced by a database constraint).
        observation.verification_status = gated.verification_status
        observation.status = "COMPLETED"

        if gated.is_low_confidence:
            outcome.warnings.append(
                {
                    "code": "AI_LOW_CONFIDENCE",
                    "message_key": "warnings.ai_low_confidence",
                    "detail": {
                        "confidence": round(result.confidence, 4),
                        "threshold": gated.high_threshold,
                    },
                }
            )

    def _run_risk(self, outcome: PipelineOutcome) -> None:
        """Assemble context and compute risk. Degrades rather than failing the request."""
        observation = outcome.observation

        signal: AiSignal | None = None
        if outcome.prediction is not None:
            signal = AiSignal(
                predicted_class=outcome.prediction.predicted_class,
                confidence=float(outcome.prediction.confidence),
                is_low_confidence=outcome.prediction.is_low_confidence,
                agent_id=outcome.prediction.predicted_agent_id,
                model_version=outcome.prediction.model_version,
            )

        try:
            context = ContextEngine(self.db, self.weather).build(observation, signal)
            outcome.context = context
        except Exception as exc:
            logger.error("context_build_failed", exc_info=exc)
            self._degrade(
                outcome,
                status=observation.status,
                verification_status=observation.verification_status,
                error_key="context",
                error={"code": "CONTEXT_FAILED", "reason": type(exc).__name__},
                warning={
                    "code": "RISK_UNAVAILABLE",
                    "message_key": "warnings.risk_unavailable",
                    "detail": {"reason": type(exc).__name__},
                },
            )
            return

        if not context.weather_available:
            outcome.warnings.append(
                {
                    "code": "WEATHER_UNAVAILABLE",
                    "message_key": "warnings.weather_unavailable",
                    "detail": {"provider": context.weather.provider if context.weather else None},
                }
            )
        elif context.weather_is_stale:
            outcome.warnings.append(
                {
                    "code": "WEATHER_STALE",
                    "message_key": "warnings.weather_stale",
                    "detail": {
                        "fetched_at": (
                            context.weather.fetched_at.isoformat()
                            if context.weather and context.weather.fetched_at
                            else None
                        )
                    },
                }
            )

        try:
            result = RuleBasedRiskEngine().evaluate(context)
        except RiskUnavailableError as exc:
            self._degrade(
                outcome,
                status="RISK_UNAVAILABLE",
                verification_status=observation.verification_status,
                error_key="risk",
                error={"code": "RISK_UNAVAILABLE", "reason": exc.message},
                warning={
                    "code": "RISK_UNAVAILABLE",
                    "message_key": "warnings.risk_unavailable",
                    "detail": {"reason": exc.message},
                },
            )
            return

        assessment = RiskAssessment(
            observation_id=observation.id,
            field_id=observation.field_id,
            agent_id=outcome.prediction.predicted_agent_id if outcome.prediction else None,
            risk_score=Decimal(str(result.risk_score)),
            risk_level=result.risk_level,
            forecast_period_start=result.forecast_period_start,
            forecast_period_end=result.forecast_period_end,
            contributing_factors=result.as_factor_dicts(),
            missing_factors=result.missing_factors,
            explanation_key=result.explanation_key,
            explanation_params=result.explanation_params,
            uncertainty=Decimal(str(result.uncertainty)),
            method=result.method,
            ruleset_version=result.ruleset_version,
            weather_is_stale=result.weather_is_stale,
        )
        self.db.add(assessment)
        self.db.flush()

        outcome.risk = assessment
        outcome.risk_result = result
        if result.missing_factors:
            outcome.warnings.append(
                {
                    "code": "RISK_PARTIAL_INPUTS",
                    "message_key": "warnings.risk_partial_inputs",
                    "detail": {"missing": [m["factor"] for m in result.missing_factors]},
                }
            )

    # ---- helpers --------------------------------------------------------------

    def _degrade(
        self,
        outcome: PipelineOutcome,
        *,
        status: str,
        verification_status: str,
        error_key: str,
        error: dict[str, Any],
        warning: dict[str, Any],
    ) -> None:
        observation = outcome.observation
        observation.status = status
        observation.verification_status = verification_status
        errors = dict(observation.processing_errors or {})
        errors[error_key] = error
        observation.processing_errors = errors
        self.db.flush()
        outcome.warnings.append(warning)

    def _finalise_status(self, outcome: PipelineOutcome) -> None:
        if outcome.observation.status == "PROCESSING":
            outcome.observation.status = "COMPLETED"
        self.db.flush()

    def _validate_coordinates(self, latitude: float, longitude: float) -> None:
        if latitude == 0 and longitude == 0:
            raise ValidationError(
                "Coordinates (0, 0) are not a valid observation location.",
                code="COORDINATES_OUT_OF_BOUNDS",
                message_key="errors.coordinates_null_island",
                details=[{"field": "latitude", "issue": "null_island"}],
            )
        minx, miny, maxx, maxy = settings.operating_bbox
        if not (minx <= longitude <= maxx and miny <= latitude <= maxy):
            raise ValidationError(
                "Coordinates are outside the configured operating area.",
                code="COORDINATES_OUT_OF_BOUNDS",
                message_key="errors.coordinates_out_of_bounds",
                details=[
                    {
                        "field": "latitude,longitude",
                        "issue": "outside_operating_bbox",
                        "operating_bbox": settings.GIS_OPERATING_BBOX,
                    }
                ],
            )

    def _resolve_field(self, field_id: uuid.UUID | None, farmer_id: uuid.UUID | None):
        if field_id is None:
            return None
        field = self.repo.get_field(field_id)
        if field is None:
            raise NotFoundError("Field")
        if farmer_id is not None and field.farmer_id != farmer_id:
            from app.core.errors import OwnershipError

            raise OwnershipError()
        return field

    def _validate_crop_context(
        self,
        crop_id: uuid.UUID | None,
        variety_id: uuid.UUID | None,
        stage_id: uuid.UUID | None,
    ) -> None:
        from app.models.catalog import CropVariety, GrowthStage

        if variety_id is not None:
            variety = self.db.get(CropVariety, variety_id)
            if variety is None:
                raise NotFoundError("Crop variety")
            if crop_id is None or variety.crop_id != crop_id:
                raise ValidationError(
                    "The selected variety does not belong to the selected crop.",
                    code="CROP_CONTEXT_MISMATCH",
                    message_key="errors.crop_context_mismatch",
                    details=[{"field": "variety_id", "issue": "crop_mismatch"}],
                )

        if stage_id is not None:
            stage = self.db.get(GrowthStage, stage_id)
            if stage is None:
                raise NotFoundError("Growth stage")
            if crop_id is None or stage.crop_id != crop_id:
                raise ValidationError(
                    "The selected growth stage does not belong to the selected crop.",
                    code="CROP_CONTEXT_MISMATCH",
                    message_key="errors.crop_context_mismatch",
                    details=[{"field": "growth_stage_id", "issue": "crop_mismatch"}],
                )

    # ---- reads ----------------------------------------------------------------

    def get_detail(self, observation_id: uuid.UUID, user) -> PipelineOutcome:
        observation = self.repo.get_for_user(observation_id, user)
        if observation is None:
            raise NotFoundError("Observation")

        return PipelineOutcome(
            observation=observation,
            image=self.repo.primary_image(observation.id),
            prediction=self.repo.latest_prediction(observation.id),
            risk=self.repo.latest_risk(observation.id),
        )

    def refresh_weather_snapshot(self, observation: Observation):
        """Weather for an observation's location, for the detail response."""
        return self.weather.get_snapshot(float(observation.latitude), float(observation.longitude))


def point_geom(latitude: float, longitude: float):
    return func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)
