"""Follow-up request schemas (Phase 7)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

OUTCOME_VALUES = ("IMPROVED", "UNCHANGED", "WORSENED", "RESOLVED", "NEEDS_EXPERT_REVIEW")


class FollowupCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation_id: uuid.UUID
    # Optional override; defaults to a risk-based interval from today.
    scheduled_for: datetime | None = None


class FollowupSubmit(BaseModel):
    """JSON part of the multipart submit request."""

    model_config = ConfigDict(extra="forbid")

    outcome: str = Field(pattern="^(" + "|".join(OUTCOME_VALUES) + ")$")
    notes: str | None = Field(default=None, max_length=2000)
