"""add team external_id

Revision ID: a2f3c8e1d4b7
Revises: 167ec731a9d1
Create Date: 2026-07-18 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a2f3c8e1d4b7'
down_revision: Union[str, None] = '167ec731a9d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('teams', sa.Column('external_id', sa.String(length=50), nullable=True))
    op.create_unique_constraint('uq_teams_external_id', 'teams', ['external_id'])


def downgrade() -> None:
    op.drop_constraint('uq_teams_external_id', 'teams', type_='unique')
    op.drop_column('teams', 'external_id')
