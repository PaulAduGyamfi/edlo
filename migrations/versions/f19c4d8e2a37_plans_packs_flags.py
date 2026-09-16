"""plans, cold opens, publishing packs, flags

Revision ID: f19c4d8e2a37
Revises: e15f3a9b7c21
Create Date: 2026-09-15 22:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f19c4d8e2a37"
down_revision: Union[str, Sequence[str], None] = "e15f3a9b7c21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "flags",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("episode_id", sa.String(length=32), nullable=False),
        sa.Column("start_ms", sa.Integer(), nullable=False),
        sa.Column("end_ms", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_flags")),
    )
    op.create_index(op.f("ix_flags_episode_id"), "flags", ["episode_id"])

    op.create_table(
        "plans",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("episode_id", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("windows", sa.Integer(), nullable=False),
        sa.Column("proposed", sa.Integer(), nullable=False),
        sa.Column("rejections", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plans")),
    )
    op.create_index(op.f("ix_plans_episode_id"), "plans", ["episode_id"])

    op.create_table(
        "cut_items",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("plan_id", sa.String(length=32), nullable=False),
        sa.Column("episode_id", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("flag_id", sa.String(length=32), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("start_ms", sa.Integer(), nullable=False),
        sa.Column("end_ms", sa.Integer(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("edited_start_ms", sa.Integer(), nullable=True),
        sa.Column("edited_end_ms", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cut_items")),
    )
    op.create_index(op.f("ix_cut_items_plan_id"), "cut_items", ["plan_id"])
    op.create_index(op.f("ix_cut_items_episode_id"), "cut_items", ["episode_id"])

    op.create_table(
        "cold_opens",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("plan_id", sa.String(length=32), nullable=False),
        sa.Column("episode_id", sa.String(length=32), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("start_ms", sa.Integer(), nullable=False),
        sa.Column("end_ms", sa.Integer(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("why", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("picked", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cold_opens")),
    )
    op.create_index(op.f("ix_cold_opens_plan_id"), "cold_opens", ["plan_id"])
    op.create_index(op.f("ix_cold_opens_episode_id"), "cold_opens", ["episode_id"])

    op.create_table(
        "publishing_packs",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("episode_id", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("chapters", sa.JSON(), nullable=False),
        sa.Column("links", sa.JSON(), nullable=False),
        sa.Column("sponsors", sa.JSON(), nullable=False),
        sa.Column("violations", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_publishing_packs")),
    )
    op.create_index(
        op.f("ix_publishing_packs_episode_id"), "publishing_packs", ["episode_id"]
    )


def downgrade() -> None:
    for table in ("publishing_packs", "cold_opens", "cut_items", "plans", "flags"):
        op.drop_table(table)
