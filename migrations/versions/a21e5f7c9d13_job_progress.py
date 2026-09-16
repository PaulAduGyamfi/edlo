"""job progress

Revision ID: a21e5f7c9d13
Revises: f19c4d8e2a37
Create Date: 2026-09-16 09:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a21e5f7c9d13"
down_revision: Union[str, Sequence[str], None] = "f19c4d8e2a37"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.add_column(sa.Column("progress", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.drop_column("progress")
