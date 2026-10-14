"""persist signal analysis results

Revision ID: 20261014_0002
Revises: 20261012_0001
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261014_0002"
down_revision = "20261012_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("waveform_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("waveforms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parameters", postgresql.JSONB(), nullable=False),
        sa.Column("metrics", postgresql.JSONB(), nullable=False),
        sa.Column("series", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("waveform_id", name="uq_analysis_waveform"),
    )


def downgrade() -> None:
    op.drop_table("analysis_results")
