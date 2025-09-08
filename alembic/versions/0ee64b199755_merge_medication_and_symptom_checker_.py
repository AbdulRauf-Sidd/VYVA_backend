"""Merge medication and symptom checker migrations

Revision ID: 0ee64b199755
Revises: cfe57d6cdd48, de2b6e6ba602
Create Date: 2025-09-08 06:09:14.784611+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0ee64b199755'
down_revision = ('cfe57d6cdd48', 'de2b6e6ba602')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass