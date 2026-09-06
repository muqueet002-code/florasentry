"""Phase 7: add followups table.

No changes to observations, ai_predictions or expert-review columns - a follow-up only
links to observations, it never touches them.

Revision ID: 0004_followups
Revises: 0003_review_note
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_followups"
down_revision: str | None = "0003_review_note"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FOLLOWUP_STATUS_VALUES = ("SCHEDULED", "SUBMITTED")
FOLLOWUP_OUTCOME_VALUES = ("IMPROVED", "UNCHANGED", "WORSENED", "RESOLVED", "NEEDS_EXPERT_REVIEW")


def upgrade() -> None:
    postgresql.ENUM(*FOLLOWUP_STATUS_VALUES, name="followup_status").create(
        op.get_bind(), checkfirst=True
    )
    postgresql.ENUM(*FOLLOWUP_OUTCOME_VALUES, name="followup_outcome").create(
        op.get_bind(), checkfirst=True
    )

    op.create_table(
        "followups",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("parent_observation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("followup_observation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(name="followup_status", create_type=False),
            server_default="SCHEDULED",
            nullable=False,
        ),
        sa.Column("outcome", postgresql.ENUM(name="followup_outcome", create_type=False), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submitted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status <> 'SUBMITTED' OR outcome IS NOT NULL",
            name="ck_followup_submitted_has_outcome",
        ),
        sa.ForeignKeyConstraint(["parent_observation_id"], ["observations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["followup_observation_id"], ["observations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["submitted_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_followups_parent", "followups", ["parent_observation_id"])
    op.create_index("ix_followups_status_scheduled", "followups", ["status", "scheduled_for"])


def downgrade() -> None:
    op.drop_table("followups")
    postgresql.ENUM(name="followup_outcome").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="followup_status").drop(op.get_bind(), checkfirst=True)
