"""merge heads

Revision ID: 5c4bf6cf6985
Revises: 28e3e3cb4f6d, 80319e3b69fe
Create Date: 2025-09-09 06:08:31.716452+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5c4bf6cf6985'
down_revision = ('28e3e3cb4f6d', '80319e3b69fe')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass