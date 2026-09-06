"""Phase 5: add observations.review_note.

No new tables. Expert review reuses the existing verification_status, verified_by,
verified_at and final_agent_id columns on `observations` - this migration only adds
the optional short note an expert can leave with a decision.

Revision ID: 0003_review_note
Revises: 0002_weather_risk
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_review_note"
down_revision: str | None = "0002_weather_risk"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("observations", sa.Column("review_note", sa.String(1000), nullable=True))


def downgrade() -> None:
    op.drop_column("observations", "review_note")
