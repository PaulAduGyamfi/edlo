"""audio file status

Revision ID: c13a0d5e9f21
Revises: ff325f6dbce7
Create Date: 2026-09-15 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c13a0d5e9f21"
down_revision: Union[str, Sequence[str], None] = "ff325f6dbce7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # batch mode: SQLite cannot ALTER COLUMN; on Postgres this is a plain ALTER.
    with op.batch_alter_table("audio_files") as batch:
        batch.add_column(
            sa.Column(
                "status", sa.String(length=16), nullable=False, server_default="ready"
            )
        )
        batch.alter_column("size_bytes", existing_type=sa.BigInteger(), nullable=True)
        batch.alter_column(
            "checksum", existing_type=sa.String(length=64), nullable=True
        )


def downgrade() -> None:
    op.execute("DELETE FROM audio_files WHERE status <> 'ready'")
    with op.batch_alter_table("audio_files") as batch:
        batch.alter_column(
            "checksum", existing_type=sa.String(length=64), nullable=False
        )
        batch.alter_column("size_bytes", existing_type=sa.BigInteger(), nullable=False)
        batch.drop_column("status")
