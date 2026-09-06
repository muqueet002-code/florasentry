"""TorchScript image-classification runner (Phase 2).

Torch is imported LAZILY inside `load()`. The application must start, serve requests
and report AI_MODEL_UNAVAILABLE honestly on a machine where torch is not installed -
which is the current state of this repository, since no weights ship with it.

Expected artifact: a TorchScript archive (`torch.jit.save`) producing per-class scores
of shape [1, len(class_list)]. Raw logits are softmaxed; already-normalised outputs are
passed through.
"""

from __future__ import annotations

import time
from pathlib import Path

from app.ai.interface import (
    ClassScore,
    InferenceFailedError,
    ModelMetadata,
    ModelRunner,
    ModelUnavailableError,
    PredictionResult,
)
from app.ai.preprocessing import softmax, to_model_input
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class TorchClassifierRunner(ModelRunner):
    def __init__(self, metadata: ModelMetadata) -> None:
        self._metadata = metadata
        self._model: object | None = None
        self._torch: object | None = None
        self._device = settings.AI_DEVICE

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def metadata(self) -> ModelMetadata:
        return self._metadata

    def load(self, artifact_path: str) -> None:
        path = Path(artifact_path)
        if not path.is_file():
            raise ModelUnavailableError(f"Model artifact not found at {artifact_path}")

        try:
            import torch  # noqa: PLC0415 - deliberate lazy import
        except ImportError as exc:
            raise ModelUnavailableError(
                "PyTorch is not installed. Install the 'ai' extra to enable inference."
            ) from exc

        try:
            model = torch.jit.load(str(path), map_location=self._device)
            model.eval()
        except Exception as exc:
            raise ModelUnavailableError(
                f"Could not load model artifact: {type(exc).__name__}"
            ) from exc

        self._torch = torch
        self._model = model
        logger.info(
            "ai_model_loaded",
            extra={"model_version": self._metadata.model_version, "device": self._device},
        )

    def warmup(self) -> None:
        if not self.is_loaded:
            return
        torch = self._torch
        assert torch is not None
        width, height = self._metadata.input_size
        with torch.inference_mode():  # type: ignore[union-attr]
            self._model(torch.zeros(1, 3, height, width, device=self._device))  # type: ignore[operator]

    def predict(self, image_bytes: bytes) -> PredictionResult:
        if not self.is_loaded:
            raise ModelUnavailableError("Model is not loaded.")

        torch = self._torch
        assert torch is not None
        started = time.perf_counter()

        try:
            chw = to_model_input(
                image_bytes,
                self._metadata.input_size,
                self._metadata.mean,
                self._metadata.std,
            )
            tensor = torch.tensor([chw], dtype=torch.float32, device=self._device)  # type: ignore[union-attr]
            with torch.inference_mode():  # type: ignore[union-attr]
                output = self._model(tensor)  # type: ignore[operator]
            scores = [float(v) for v in output[0].tolist()]
        except Exception as exc:
            logger.error("ai_inference_failed", extra={"error": type(exc).__name__})
            raise InferenceFailedError(type(exc).__name__) from exc

        classes = self._metadata.class_list
        if len(scores) != len(classes):
            raise InferenceFailedError(
                f"Model returned {len(scores)} scores but the registry declares "
                f"{len(classes)} classes."
            )

        # Treat as logits unless the output already looks like a distribution.
        total = sum(scores)
        already_normalised = all(0.0 <= s <= 1.0 for s in scores) and abs(total - 1.0) < 0.01
        probabilities = scores if already_normalised else softmax(scores)

        ranked = sorted(
            (
                ClassScore(label=c, confidence=p)
                for c, p in zip(classes, probabilities, strict=True)
            ),
            key=lambda cs: cs.confidence,
            reverse=True,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        return PredictionResult(
            predicted_class=ranked[0].label,
            confidence=ranked[0].confidence,
            top_k=ranked[: settings.AI_TOP_K],
            inference_ms=elapsed_ms,
            runtime_device=self._device,
        )
