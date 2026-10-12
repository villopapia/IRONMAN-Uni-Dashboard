"""intervals race flag, StairStepper -> walk

Revision ID: 8f2b6c1d4e7a
Revises: 3c242867525f
Create Date: 2026-10-11 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f2b6c1d4e7a'
down_revision: Union[str, None] = '3c242867525f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('intervals_activities', schema=None) as batch_op:
        batch_op.add_column(sa.Column('race', sa.Boolean(), server_default=sa.false(), nullable=False))
    # SPORT_MAP gained StairStepper -> walk: re-bucket the rows stored as "other".
    op.execute("UPDATE activities SET sport = 'walk' WHERE sport_type = 'StairStepper'")
    op.execute("UPDATE intervals_activities SET sport = 'walk' WHERE type = 'StairStepper'")


def downgrade() -> None:
    op.execute("UPDATE intervals_activities SET sport = 'other' WHERE type = 'StairStepper'")
    op.execute("UPDATE activities SET sport = 'other' WHERE sport_type = 'StairStepper'")
    with op.batch_alter_table('intervals_activities', schema=None) as batch_op:
        batch_op.drop_column('race')
