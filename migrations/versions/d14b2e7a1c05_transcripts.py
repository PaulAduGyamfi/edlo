"""transcripts

Revision ID: d14b2e7a1c05
Revises: c13a0d5e9f21
Create Date: 2026-09-15 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d14b2e7a1c05"
down_revision: Union[str, Sequence[str], None] = "c13a0d5e9f21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "transcripts",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("audio_file_id", sa.String(length=32), nullable=False),
        sa.Column("episode_id", sa.String(length=32), nullable=False),
        sa.Column("storage_key", sa.String(length=300), nullable=False),
        sa.Column("engine", sa.String(length=64), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("segment_count", sa.Integer(), nullable=False),
        sa.Column("audio_checksum", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transcripts")),
    )
    op.create_index(
        op.f("ix_transcripts_audio_file_id"), "transcripts", ["audio_file_id"]
    )
    op.create_index(op.f("ix_transcripts_episode_id"), "transcripts", ["episode_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_transcripts_episode_id"), table_name="transcripts")
    op.drop_index(op.f("ix_transcripts_audio_file_id"), table_name="transcripts")
    op.drop_table("transcripts")
