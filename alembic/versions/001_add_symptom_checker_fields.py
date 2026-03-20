"""add_symptom_checker_fields

Revision ID: 001_add_symptom_checker_fields
Revises: 
Create Date: 2025-01-20 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_add_symptom_checker_fields'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add user_id column with foreign key to users table
    op.add_column('symptom_checker_responses', 
                   sa.Column('user_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_symptom_checker_responses_user_id'), 
                    'symptom_checker_responses', ['user_id'], unique=False)
    op.create_foreign_key('fk_symptom_checker_responses_user_id', 
                          'symptom_checker_responses', 'users', ['user_id'], ['id'])
    
    # Add call_duration_secs column
    op.add_column('symptom_checker_responses', 
                   sa.Column('call_duration_secs', sa.Integer(), nullable=True))
    
    # Add call_timestamp column
    op.add_column('symptom_checker_responses', 
                   sa.Column('call_timestamp', sa.DateTime(timezone=True), nullable=True))
    
    # Add vitals_data JSON column
    op.add_column('symptom_checker_responses', 
                   sa.Column('vitals_data', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    
    # Add vitals_ai_summary column
    op.add_column('symptom_checker_responses', 
                   sa.Column('vitals_ai_summary', sa.Text(), nullable=True))
    
    # Add symptoms_ai_summary column
    op.add_column('symptom_checker_responses', 
                   sa.Column('symptoms_ai_summary', sa.Text(), nullable=True))


def downgrade() -> None:
    # Remove symptoms_ai_summary column
    op.drop_column('symptom_checker_responses', 'symptoms_ai_summary')
    
    # Remove vitals_ai_summary column
    op.drop_column('symptom_checker_responses', 'vitals_ai_summary')
    
    # Remove vitals_data column
    op.drop_column('symptom_checker_responses', 'vitals_data')
    
    # Remove call_timestamp column
    op.drop_column('symptom_checker_responses', 'call_timestamp')
    
    # Remove call_duration_secs column
    op.drop_column('symptom_checker_responses', 'call_duration_secs')
    
    # Remove foreign key, index, and user_id column
    op.drop_constraint('fk_symptom_checker_responses_user_id', 
                      'symptom_checker_responses', type_='foreignkey')
    op.drop_index(op.f('ix_symptom_checker_responses_user_id'), 
                  table_name='symptom_checker_responses')
    op.drop_column('symptom_checker_responses', 'user_id')

