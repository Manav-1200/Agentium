"""skill_system

Revision ID: 004
Revises: 003_user_preferences
Create Date: 2026-02-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003_skill_system'
down_revision = '002_ab_testing'
branch_labels = None
depends_on = None


def upgrade():
    # Create skills table
    op.create_table(
        'skills',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('agentium_id', sa.String(length=20), unique=True, nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        # FIX: Added soft-delete columns that ORM expects
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('skill_id', sa.String(length=50), nullable=False),
        sa.Column('skill_name', sa.String(length=100), nullable=False),
        sa.Column('display_name', sa.String(length=200), nullable=False),
        sa.Column('skill_type', sa.String(length=50), nullable=False),
        sa.Column('domain', sa.String(length=50), nullable=False),
        sa.Column('tags', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('complexity', sa.String(length=20), nullable=False),
        sa.Column('chroma_id', sa.String(length=100), nullable=False),
        sa.Column('chroma_collection', sa.String(length=50), nullable=True),
        sa.Column('embedding_model', sa.String(length=100), nullable=True),
        sa.Column('creator_tier', sa.String(length=20), nullable=False),
        sa.Column('creator_id', sa.String(length=20), nullable=False),
        sa.Column('parent_skill_id', sa.String(length=50), nullable=True),
        sa.Column('task_origin', sa.String(length=50), nullable=True),
        sa.Column('success_rate', sa.Float(), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=True),
        sa.Column('retrieval_count', sa.Integer(), nullable=True),
        sa.Column('last_retrieved', sa.DateTime(), nullable=True),
        sa.Column('constitution_compliant', sa.Boolean(), nullable=True),
        sa.Column('verification_status', sa.String(length=20), nullable=True),
        sa.Column('verified_by', sa.String(length=20), nullable=True),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.Column('rejection_reason', sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(['parent_skill_id'], ['skills.skill_id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('skill_id')
    )
    op.create_index('ix_skills_skill_id', 'skills', ['skill_id'], unique=True)
    op.create_index('ix_skills_agentium_id', 'skills', ['agentium_id'], unique=True)
    op.create_index('ix_skills_domain', 'skills', ['domain'])
    op.create_index('ix_skills_skill_type', 'skills', ['skill_type'])
    op.create_index('ix_skills_verification_status', 'skills', ['verification_status'])

    # Create skill_submissions table
    op.create_table(
        'skill_submissions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('agentium_id', sa.String(length=20), unique=True, nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('submission_id', sa.String(length=50), nullable=False),
        sa.Column('skill_id', sa.String(length=50), nullable=False),
        sa.Column('submitted_by', sa.String(length=20), nullable=False),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('council_vote_id', sa.String(length=50), nullable=True),
        sa.Column('reviewed_by', sa.String(length=20), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('review_notes', sa.String(length=1000), nullable=True),
        sa.Column('skill_data', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(['skill_id'], ['skills.skill_id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('submission_id')
    )
    op.create_index('ix_skill_submissions_status', 'skill_submissions', ['status'])


def downgrade():
    op.drop_index('ix_skill_submissions_status', table_name='skill_submissions')
    op.drop_table('skill_submissions')
    op.drop_index('ix_skills_verification_status', table_name='skills')
    op.drop_index('ix_skills_skill_type', table_name='skills')
    op.drop_index('ix_skills_domain', table_name='skills')
    op.drop_index('ix_skills_agentium_id', table_name='skills')
    op.drop_index('ix_skills_skill_id', table_name='skills')
    op.drop_table('skills')