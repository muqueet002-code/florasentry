"""ORM model registry.

Importing this package registers every model on `Base.metadata`, which Alembic's
autogenerate and the test harness both rely on. Import order matters only insofar as
relationship targets must be importable by name.
"""

from app.db.base import Base
from app.models.catalog import (
    AgentCrop,
    AgentSymptom,
    Crop,
    CropVariety,
    DiseasePestCatalog,
    GrowthStage,
    Symptom,
)
from app.models.farmer import Farmer, Field
from app.models.observation import Observation, ObservationImage
from app.models.prediction import AiModelRegistry, AiPrediction
from app.models.provenance import AuditLog, DataSource
from app.models.region import AdminRegion
from app.models.user import RefreshToken, User

__all__ = [
    "AdminRegion",
    "AgentCrop",
    "AgentSymptom",
    "AiModelRegistry",
    "AiPrediction",
    "AuditLog",
    "Base",
    "Crop",
    "CropVariety",
    "DataSource",
    "DiseasePestCatalog",
    "Farmer",
    "Field",
    "GrowthStage",
    "Observation",
    "ObservationImage",
    "RefreshToken",
    "Symptom",
    "User",
]
