"""Add custom_capabilities field to agents table for Phase 3

Revision ID: add_custom_capabilities
Revises: 
Create Date: 2026-02-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_custom_capabilities'
down_revision = None  # TODO: Set this to your current latest migration revision
branch_labels = None
depends_on = None


def upgrade():
    """
    Add custom_capabilities column to agents table.
    This enables dynamic capability granting/revoking for Phase 3.
    """
    # Add custom_capabilities column (stores JSON as Text)
    op.add_column(
        'agents',
        sa.Column(
            'custom_capabilities',
            sa.Text(),
            nullable=True,
            comment='JSON: {"granted": [...], "revoked": [...]}'
        )
    )
    
    # Initialize existing agents with empty JSON
    op.execute(
        """
        UPDATE agents 
        SET custom_capabilities = '{"granted": [], "revoked": []}'
        WHERE custom_capabilities IS NULL
        """
    )
    
    print("✅ Phase 3 Migration: Added custom_capabilities column to agents table")


def downgrade():
    """
    Remove custom_capabilities column.
    """
    op.drop_column('agents', 'custom_capabilities')
    print("⏪ Phase 3 Migration: Removed custom_capabilities column from agents table")