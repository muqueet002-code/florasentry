"""Inference orchestration and the confidence gate (Phase 2).

Resolves the active model from `ai_model_registry`, runs it, and applies the
confidence gate that decides whether a result is shown as a preliminary assessment or
routed to expert review.

The gate is the mechanism that keeps a prediction from becoming a diagnosis:
  confidence >= high threshold  -> PREDICTED       (preliminary, clearly labelled)
  confidence <  high threshold  -> PENDING_REVIEW  (queued for an expert)

Thresholds are per-model registry values, never hard-coded, because a correct threshold
can only come from a real evaluation of that specific model.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.interface import (
    ClassScore,
    InferenceFailedError,
    ModelMetadata,
    ModelRunner,
    ModelUnavailableError,
    PredictionResult,
)
from app.ai.runners.torch_classifier import TorchClassifierRunner
from app.core.config import settings
from app.core.logging import get_logger
from app.models.catalog import DiseasePestCatalog
from app.models.prediction import AiModelRegistry

logger = get_logger(__name__)

# Bounds concurrent inference so a burst of uploads cannot starve the API of CPU.
_inference_semaphore = threading.Semaphore(settings.AI_MAX_CONCURRENT_INFERENCE)

RUNNERS: dict[str, type[ModelRunner]] = {
    "app.ai.runners.torch_classifier.TorchClassifierRunner": TorchClassifierRunner,
}


@dataclass(frozen=True)
class GatedPrediction:
    """An inference result plus the verification status the gate assigned."""

    result: PredictionResult
    model_version: str
    is_low_confidence: bool
    verification_status: str  # PREDICTED | PENDING_REVIEW
    high_threshold: float
    low_threshold: float


class AiUnavailable(Exception):
    """No model is usable. Callers degrade; they never substitute a prediction."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class _RunnerCache:
    """Process-wide cache of the loaded runner, keyed by model version."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._version: str | None = None
        self._runner: ModelRunner | None = None
        self._last_error: str | None = None

    def get(self, row: AiModelRegistry) -> ModelRunner:
        with self._lock:
            if self._runner is not None and self._version == row.model_version:
                return self._runner

            runner_cls = RUNNERS.get(row.runner_class)
            if runner_cls is None:
                self._last_error = f"Unknown runner class: {row.runner_class}"
                raise ModelUnavailableError(self._last_error)

            try:
                width, height = (int(x) for x in row.input_size.lower().split("x"))
            except ValueError as exc:
                self._last_error = f"Invalid input_size '{row.input_size}'"
                raise ModelUnavailableError(self._last_error) from exc

            metadata = ModelMetadata(
                model_version=row.model_version,
                task=row.task,
                framework=row.framework,
                class_list=list(row.class_list),
                input_size=(width, height),
            )
            runner = runner_cls(metadata)  # type: ignore[call-arg]
            artifact = str(settings.AI_MODEL_ARTIFACT_DIR).rstrip("/") + "/" + row.artifact_key

            try:
                runner.load(artifact)
                runner.warmup()
            except ModelUnavailableError as exc:
                self._last_error = str(exc)
                raise

            self._runner = runner
            self._version = row.model_version
            self._last_error = None
            return runner

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def reset(self) -> None:
        with self._lock:
            self._runner = None
            self._version = None
            self._last_error = None


_cache = _RunnerCache()


def reset_runner_cache() -> None:
    """Force the next call to reload. Used by tests and by model activation."""
    _cache.reset()


def get_active_model(db: Session) -> AiModelRegistry | None:
    """The active CLASSIFICATION model, or None if the registry has no active row."""
    return (
        db.execute(
            select(AiModelRegistry).where(
                AiModelRegistry.is_active.is_(True),
                AiModelRegistry.task == "CLASSIFICATION",
            )
        )
        .scalars()
        .first()
    )


def model_status(db: Session) -> dict[str, object]:
    """Honest AI status for /health and /ai/models/active."""
    if not settings.AI_ENABLED:
        return {
            "ok": False,
            "state": "DISABLED",
            "detail": "AI_ENABLED is false.",
            "model_version": None,
        }

    row = get_active_model(db)
    if row is None:
        return {
            "ok": False,
            "state": "AI_MODEL_UNAVAILABLE",
            "detail": "No active model is registered. No weights ship with this repository.",
            "model_version": None,
        }

    try:
        _cache.get(row)
    except ModelUnavailableError as exc:
        return {
            "ok": False,
            "state": "AI_MODEL_UNAVAILABLE",
            "detail": str(exc),
            "model_version": row.model_version,
        }

    return {
        "ok": True,
        "state": "READY",
        "detail": None,
        "model_version": row.model_version,
        "class_list": list(row.class_list),
        "high_confidence_threshold": float(row.high_confidence_threshold),
        "low_confidence_threshold": float(row.low_confidence_threshold),
        # Never pre-filled: null until a real evaluation run populates it.
        "evaluation_metrics": row.evaluation_metrics,
    }


def run_inference(db: Session, image_bytes: bytes) -> GatedPrediction:
    """Run the active model and apply the confidence gate.

    Raises:
        AiUnavailable       - no usable model; the caller degrades.
        InferenceFailedError - the model raised; the caller records the failure.
    """
    if not settings.AI_ENABLED:
        raise AiUnavailable("AI_ENABLED is false")

    row = get_active_model(db)
    if row is None:
        raise AiUnavailable("No active model registered")

    try:
        runner = _cache.get(row)
    except ModelUnavailableError as exc:
        raise AiUnavailable(str(exc)) from exc

    acquired = _inference_semaphore.acquire(timeout=settings.AI_INFERENCE_TIMEOUT_SEC)
    if not acquired:
        raise InferenceFailedError("Inference queue timed out")
    try:
        result = runner.predict(image_bytes)
    finally:
        _inference_semaphore.release()

    high = float(row.high_confidence_threshold)
    low = float(row.low_confidence_threshold)
    is_low = result.confidence < high

    logger.info(
        "ai_prediction",
        extra={
            "model_version": row.model_version,
            "confidence": round(result.confidence, 4),
            "is_low_confidence": is_low,
            "inference_ms": result.inference_ms,
        },
    )

    return GatedPrediction(
        result=result,
        model_version=row.model_version,
        is_low_confidence=is_low,
        # A prediction the model is not confident about is never presented as an
        # assessment; it goes to a human.
        verification_status="PENDING_REVIEW" if is_low else "PREDICTED",
        high_threshold=high,
        low_threshold=low,
    )


def resolve_agent_id(db: Session, class_code: str) -> uuid.UUID | None:
    """Map a raw model label to a catalogue agent, if one exists.

    An unmapped label is not an error: the raw class is always stored, and the
    prediction simply has no catalogue link.
    """
    agent = (
        db.execute(select(DiseasePestCatalog).where(DiseasePestCatalog.code == class_code))
        .scalars()
        .first()
    )
    return agent.id if agent else None


def top_k_payload(scores: list[ClassScore]) -> list[dict[str, object]]:
    return [{"class": s.label, "confidence": round(s.confidence, 4)} for s in scores]


def to_decimal(value: float) -> Decimal:
    return Decimal(str(round(value, 4)))
