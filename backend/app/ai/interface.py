"""Model-runner interface and DTOs (Phase 2).

Nothing above this interface knows the framework, the architecture or the class list.
Swapping a model is a registry row plus a runner class - no caller changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ClassScore:
    label: str
    confidence: float


@dataclass(frozen=True)
class ModelMetadata:
    model_version: str
    task: str  # CLASSIFICATION | DETECTION
    framework: str
    class_list: list[str]
    input_size: tuple[int, int]
    # Normalisation lives with the model, not in the calling code, so a model swap
    # cannot silently break preprocessing.
    mean: tuple[float, float, float] = (0.485, 0.456, 0.406)
    std: tuple[float, float, float] = (0.229, 0.224, 0.225)


@dataclass(frozen=True)
class PredictionResult:
    predicted_class: str
    confidence: float
    top_k: list[ClassScore] = field(default_factory=list)
    severity_estimate: float | None = None
    inference_ms: int = 0
    runtime_device: str = "cpu"


class ModelUnavailableError(RuntimeError):
    """No usable model. The caller must degrade, never substitute a prediction."""


class InferenceFailedError(RuntimeError):
    """Inference raised or timed out. No prediction is produced."""


class ModelRunner(ABC):
    """Contract every inference backend implements."""

    @abstractmethod
    def load(self, artifact_path: str) -> None:
        """Load weights. Raises ModelUnavailableError if it cannot."""

    @abstractmethod
    def predict(self, image_bytes: bytes) -> PredictionResult:
        """Run inference. Raises InferenceFailedError on any failure."""

    @abstractmethod
    def metadata(self) -> ModelMetadata: ...

    @abstractmethod
    def warmup(self) -> None:
        """Optional: pay initialisation cost before the first real request."""

    @property
    @abstractmethod
    def is_loaded(self) -> bool: ...
