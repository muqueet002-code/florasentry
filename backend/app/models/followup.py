"""Follow-up monitoring model (Phase 7).

A follow-up NEVER overwrites the parent observation or its expert validation - it only
links to them. When the farmer submits with a photo, a brand new `Observation` row is
created through the existing pipeline (image validation, AI, weather, risk) and linked
via `followup_observation_id`; the parent's own prediction/verification_status/
final_agent_id are untouched (TRD 20.2: pipeline state vs truth state, never collapsed).

No separate `source_type`/provenance column here: a follow-up's "is this real or
demo" question is answered by the `source_type` on the observations it links to
(the parent, and the child if one was created), so provenance is never duplicated
and cannot drift from the observation it describes.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, followup_outcome_enum, followup_status_enum, uuid_pk


class Followup(Base, TimestampMixin):
    __tablename__ = "followups"

    id: Mapped[uuid.UUID] = uuid_pk()

    parent_observation_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("observations.id", ondelete="CASCADE"), nullable=False
    )
    # Set only once the farmer submits with a photo (reuses the full observation
    # pipeline). A note-only submission leaves this null.
    followup_observation_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("observations.id", ondelete="SET NULL"), nullable=True
    )

    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        followup_status_enum, nullable=False, server_default="SCHEDULED"
    )
    # The farmer's own assessment of current condition. Set only on submission.
    outcome: Mapped[str | None] = mapped_column(followup_outcome_enum, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status <> 'SUBMITTED' OR outcome IS NOT NULL",
            name="ck_followup_submitted_has_outcome",
        ),
        Index("ix_followups_parent", "parent_observation_id"),
        Index("ix_followups_status_scheduled", "status", "scheduled_for"),
    )
