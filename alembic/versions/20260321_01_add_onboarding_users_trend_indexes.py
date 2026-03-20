"""add onboarding users trend indexes

Revision ID: 20260321_01
Revises: 
Create Date: 2026-03-21 00:00:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260321_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_onboarding_users_org_created_at",
        "onboarding_users",
        ["organization_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_onboarding_users_org_onboarded_at",
        "onboarding_users",
        ["organization_id", "onboarded_at"],
        unique=False,
    )
    op.create_index(
        "ix_onboarding_users_org_called_at",
        "onboarding_users",
        ["organization_id", "called_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_onboarding_users_org_called_at", table_name="onboarding_users")
    op.drop_index("ix_onboarding_users_org_onboarded_at", table_name="onboarding_users")
    op.drop_index("ix_onboarding_users_org_created_at", table_name="onboarding_users")
