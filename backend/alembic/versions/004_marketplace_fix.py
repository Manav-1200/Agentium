"""Add missing BaseEntity columns to tool_marketplace_listings

Revision ID: 004_marketplace_fix
Revises: 003_skill_system
Create Date: 2026-02-28

This migration adds the missing BaseEntity columns that the ORM expects:
- agentium_id (unique string identifier)
- created_at (timestamp)
- updated_at (timestamp)  
- deleted_at (soft delete timestamp)
- is_active (boolean flag)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '004_marketplace_fix'
down_revision = '003_skill_system'
branch_labels = None
depends_on = None


def upgrade():
    # Add missing BaseEntity columns to tool_marketplace_listings

    # Check if columns exist before adding (for idempotency)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = {col['name'] for col in inspector.get_columns('tool_marketplace_listings')}
    
    # Add agentium_id column (unique identifier for BaseEntity)
    if 'agentium_id' not in existing_columns:
        op.add_column(
            'tool_marketplace_listings',
            sa.Column('agentium_id', sa.String(20), unique=True, nullable=True)
        )
        # Create unique index for agentium_id
        op.create_index(
            'ix_tool_marketplace_listings_agentium_id',
            'tool_marketplace_listings',
            ['agentium_id'],
            unique=True
        )
    
    # Add is_active column (soft delete flag)
    if 'is_active' not in existing_columns:
        op.add_column(
            'tool_marketplace_listings',
            sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False)
        )
    
    # Add created_at timestamp
    if 'created_at' not in existing_columns:
        op.add_column(
            'tool_marketplace_listings',
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False)
        )
    
    # Add updated_at timestamp
    if 'updated_at' not in existing_columns:
        op.add_column(
            'tool_marketplace_listings',
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False)
        )
    
    # Add deleted_at timestamp (for soft deletes)
    if 'deleted_at' not in existing_columns:
        op.add_column(
            'tool_marketplace_listings',
            sa.Column('deleted_at', sa.DateTime(), nullable=True)
        )
    
    # Populate existing rows with default values
    op.execute("""
        UPDATE tool_marketplace_listings 
        SET agentium_id = 'MKTL' || LPAD(id::text, 5, '0'),
            is_active = true,
            created_at = COALESCE(published_at, NOW()),
            updated_at = NOW()
        WHERE agentium_id IS NULL
    """)
    
    print("✅ Added BaseEntity columns to tool_marketplace_listings")


def downgrade():
    # Remove the added columns in reverse order
    try:
        op.drop_index('ix_tool_marketplace_listings_agentium_id', table_name='tool_marketplace_listings')
    except Exception:
        pass
    
    columns_to_drop = ['deleted_at', 'updated_at', 'created_at', 'is_active', 'agentium_id']
    for col in columns_to_drop:
        try:
            op.drop_column('tool_marketplace_listings', col)
        except Exception as e:
            print(f"Note: could not drop column {col}: {e}")