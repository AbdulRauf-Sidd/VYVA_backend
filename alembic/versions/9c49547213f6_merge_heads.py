"""merge heads

Revision ID: 9c49547213f6
Revises: cfe57d6cdd48, de2b6e6ba602
Create Date: 2025-09-07 17:48:56.094490+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9c49547213f6'
down_revision = ('cfe57d6cdd48', 'de2b6e6ba602')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass