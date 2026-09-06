"""Expert review request schema (Phase 5)."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["CONFIRM", "CORRECT", "REJECT"]
    # Required for CORRECT; must reference an existing disease_pest_catalog row.
    corrected_agent_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _correct_requires_agent(self) -> ReviewDecision:
        if self.decision == "CORRECT" and self.corrected_agent_id is None:
            raise ValueError("corrected_agent_id is required when decision is CORRECT")
        return self
