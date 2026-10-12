"""intervals hr zone times + distance

Revision ID: c41d7e90ab52
Revises: 8f2b6c1d4e7a
Create Date: 2026-10-12 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c41d7e90ab52'
down_revision: Union[str, None] = '8f2b6c1d4e7a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Filled by a full re-sync: python -m app.services.intervals_sync resync
    with op.batch_alter_table('intervals_activities', schema=None) as batch_op:
        batch_op.add_column(sa.Column('hr_zone_secs', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('distance_m', sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('intervals_activities', schema=None) as batch_op:
        batch_op.drop_column('distance_m')
        batch_op.drop_column('hr_zone_secs')
