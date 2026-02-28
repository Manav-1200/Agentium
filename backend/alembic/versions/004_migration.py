"""Comprehensive Migration 004 - BaseEntity fixes, schema corrections, and utilities

Revision ID: 004_migration
Revises: 003_skill_system
Create Date: 2026-02-28

This migration consolidates and fixes:
1. Adds missing BaseEntity columns to tool_marketplace_listings
   - agentium_id, is_active, created_at, updated_at, deleted_at
2. Fixes monitoring_alerts.agentium_id to be nullable (matches ORM behavior)
3. Creates PostgreSQL backup function (alternative to pg_dump binary)
4. Ensures idempotency - safe to run multiple times
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect, text

# revision identifiers
revision = '004_migration'
down_revision = '003_skill_system'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    
    print("🚀 Starting comprehensive migration 004...")
    
    # =========================================================================
    # 1. FIX tool_marketplace_listings - Add missing BaseEntity columns
    # =========================================================================
    print("\n🔧 Checking tool_marketplace_listings schema...")
    
    existing_columns = {col['name'] for col in inspector.get_columns('tool_marketplace_listings')}
    
    # Add agentium_id column (unique identifier for BaseEntity)
    if 'agentium_id' not in existing_columns:
        op.add_column(
            'tool_marketplace_listings',
            sa.Column('agentium_id', sa.String(20), unique=True, nullable=True)
        )
        op.create_index(
            'ix_tool_marketplace_listings_agentium_id',
            'tool_marketplace_listings',
            ['agentium_id'],
            unique=True
        )
        print("  ✅ Added agentium_id column")
    else:
        print("  ℹ️  agentium_id already exists")
    
    # Add is_active column (soft delete flag)
    if 'is_active' not in existing_columns:
        op.add_column(
            'tool_marketplace_listings',
            sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False)
        )
        print("  ✅ Added is_active column")
    else:
        print("  ℹ️  is_active already exists")
    
    # Add created_at timestamp
    if 'created_at' not in existing_columns:
        op.add_column(
            'tool_marketplace_listings',
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False)
        )
        print("  ✅ Added created_at column")
    else:
        print("  ℹ️  created_at already exists")
    
    # Add updated_at timestamp
    if 'updated_at' not in existing_columns:
        op.add_column(
            'tool_marketplace_listings',
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False)
        )
        print("  ✅ Added updated_at column")
    else:
        print("  ℹ️  updated_at already exists")
    
    # Add deleted_at timestamp (for soft deletes)
    if 'deleted_at' not in existing_columns:
        op.add_column(
            'tool_marketplace_listings',
            sa.Column('deleted_at', sa.DateTime(), nullable=True)
        )
        print("  ✅ Added deleted_at column")
    else:
        print("  ℹ️  deleted_at already exists")
    
    # Populate existing rows with default values if needed
    # Only populate if we just added agentium_id or if there are NULL values
    null_count = conn.execute(text("""
        SELECT COUNT(*) FROM tool_marketplace_listings WHERE agentium_id IS NULL
    """)).scalar()
    
    if null_count > 0:
        op.execute("""
            UPDATE tool_marketplace_listings 
            SET agentium_id = 'MKTL' || LPAD(id::text, 5, '0'),
                is_active = COALESCE(is_active, true),
                created_at = COALESCE(created_at, published_at, NOW()),
                updated_at = COALESCE(updated_at, NOW())
            WHERE agentium_id IS NULL
        """)
        print(f"  ✅ Populated default values for {null_count} existing rows")
    else:
        print("  ℹ️  No rows need population")
    
    # =========================================================================
    # 2. FIX monitoring_alerts.agentium_id - make nullable to match ORM
    # =========================================================================
    print("\n🔧 Checking monitoring_alerts schema...")
    
    columns = {col['name']: col for col in inspector.get_columns('monitoring_alerts')}
    
    if 'agentium_id' in columns:
        # Check if it's currently NOT NULL
        result = conn.execute(text("""
            SELECT is_nullable, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'monitoring_alerts' 
            AND column_name = 'agentium_id'
        """)).fetchone()
        
        if result and result[0] == 'NO':
            print("  → Altering monitoring_alerts.agentium_id to nullable...")
            op.execute("""
                ALTER TABLE monitoring_alerts 
                ALTER COLUMN agentium_id DROP NOT NULL
            """)
            print("  ✅ monitoring_alerts.agentium_id is now nullable")
        else:
            print("  ℹ️  monitoring_alerts.agentium_id is already nullable")
    else:
        print("  ⚠️  monitoring_alerts.agentium_id column not found - creating it as nullable")
        op.add_column(
            'monitoring_alerts',
            sa.Column('agentium_id', sa.String(10), unique=True, nullable=True)
        )
        op.create_index(
            'ix_monitoring_alerts_agentium_id',
            'monitoring_alerts',
            ['agentium_id'],
            unique=True
        )
        print("  ✅ Created monitoring_alerts.agentium_id as nullable")
    
    # =========================================================================
    # 3. Create backup function (alternative to pg_dump binary)
    # =========================================================================
    print("\n🔧 Creating backup helper function...")
    
    op.execute("""
        CREATE OR REPLACE FUNCTION create_backup_sql()
        RETURNS text AS $$
        DECLARE
            result text := '';
            rec record;
        BEGIN
            -- Get schema creation SQL for all tables
            FOR rec IN 
                SELECT 'CREATE TABLE IF NOT EXISTS ' || tablename || ' (' || 
                    string_agg(
                        column_name || ' ' || 
                        CASE 
                            WHEN data_type = 'character varying' AND character_maximum_length IS NOT NULL 
                                THEN 'varchar(' || character_maximum_length || ')'
                            WHEN data_type = 'character varying' 
                                THEN 'varchar'
                            WHEN data_type = 'integer' 
                                THEN 'integer'
                            WHEN data_type = 'bigint' 
                                THEN 'bigint'
                            WHEN data_type = 'boolean' 
                                THEN 'boolean'
                            WHEN data_type = 'timestamp without time zone' 
                                THEN 'timestamp'
                            WHEN data_type = 'timestamp with time zone' 
                                THEN 'timestamptz'
                            WHEN data_type = 'text' 
                                THEN 'text'
                            WHEN data_type = 'json' 
                                THEN 'json'
                            WHEN data_type = 'jsonb' 
                                THEN 'jsonb'
                            WHEN data_type = 'uuid' 
                                THEN 'uuid'
                            WHEN data_type = 'numeric' 
                                THEN 'numeric'
                            WHEN data_type = 'double precision' 
                                THEN 'float'
                            WHEN data_type = 'real' 
                                THEN 'real'
                            ELSE data_type
                        END ||
                        CASE WHEN is_nullable = 'NO' THEN ' NOT NULL' ELSE '' END,
                        ', ' ORDER BY ordinal_position
                    ) || ');' as ddl
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name NOT LIKE 'pg_%'
                AND table_name NOT LIKE 'sql_%'
                GROUP BY tablename
            LOOP
                result := result || rec.ddl || E'\n\n';
            END LOOP;
            
            -- Add comment with timestamp
            result := result || '-- Backup generated at: ' || NOW()::text || E'\n';
            
            RETURN result;
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("  ✅ Created create_backup_sql() function")
    
    # Also create a simple table backup function that doesn't require pg_dump
    op.execute("""
        CREATE OR REPLACE FUNCTION backup_table_to_json(table_name text)
        RETURNS json AS $$
        DECLARE
            result json;
            query text;
        BEGIN
            query := 'SELECT json_agg(row_to_json(t)) FROM ' || quote_ident(table_name) || ' t';
            EXECUTE query INTO result;
            RETURN COALESCE(result, '[]'::json);
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("  ✅ Created backup_table_to_json() function")
    
    # =========================================================================
    # 4. Additional fixes - Ensure proper indexes exist
    # =========================================================================
    print("\n🔧 Checking indexes...")
    
    # Check if monitoring_alerts has proper indexes
    existing_indexes = {idx['name'] for idx in inspector.get_indexes('monitoring_alerts')}
    
    if 'ix_monitoring_alerts_agentium_id' not in existing_indexes:
        try:
            op.create_index(
                'ix_monitoring_alerts_agentium_id',
                'monitoring_alerts',
                ['agentium_id'],
                unique=True
            )
            print("  ✅ Added index on monitoring_alerts.agentium_id")
        except Exception as e:
            print(f"  ℹ️  Could not add index (may already exist): {e}")
    
    print("\n" + "="*70)
    print("✅ Migration 004_migration completed successfully!")
    print("="*70)
    print("Changes applied:")
    print("  • tool_marketplace_listings: BaseEntity columns added")
    print("  • monitoring_alerts: agentium_id is now nullable")
    print("  • PostgreSQL backup functions created (pg_dump alternative)")
    print("="*70)


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    
    print("🔄 Starting downgrade of migration 004...")
    
    # =========================================================================
    # 1. Restore monitoring_alerts.agentium_id to NOT NULL
    # =========================================================================
    try:
        # Only restore if there are no NULL values
        null_count = conn.execute(text("""
            SELECT COUNT(*) FROM monitoring_alerts WHERE agentium_id IS NULL
        """)).scalar()
        
        if null_count == 0:
            op.execute("""
                ALTER TABLE monitoring_alerts 
                ALTER COLUMN agentium_id SET NOT NULL
            """)
            print("Restored monitoring_alerts.agentium_id to NOT NULL")
        else:
            print(f"Cannot restore NOT NULL: {null_count} rows have NULL agentium_id")
    except Exception as e:
        print(f"Note: could not restore monitoring_alerts constraint: {e}")
    
    # =========================================================================
    # 2. Remove BaseEntity columns from tool_marketplace_listings
    # =========================================================================
    try:
        op.drop_index('ix_tool_marketplace_listings_agentium_id', table_name='tool_marketplace_listings')
    except Exception:
        pass
    
    columns_to_drop = ['deleted_at', 'updated_at', 'created_at', 'is_active', 'agentium_id']
    for col in columns_to_drop:
        try:
            op.drop_column('tool_marketplace_listings', col)
            print(f"Dropped column {col}")
        except Exception as e:
            print(f"Note: could not drop column {col}: {e}")
    
    # =========================================================================
    # 3. Drop backup functions
    # =========================================================================
    try:
        op.execute("DROP FUNCTION IF EXISTS create_backup_sql()")
        print("Dropped create_backup_sql() function")
    except Exception as e:
        print(f"Note: could not drop backup function: {e}")
    
    try:
        op.execute("DROP FUNCTION IF EXISTS backup_table_to_json(text)")
        print("Dropped backup_table_to_json() function")
    except Exception as e:
        print(f"Note: could not drop backup function: {e}")
    
    # =========================================================================
    # 4. Drop monitoring_alerts index if we created it
    # =========================================================================
    try:
        op.drop_index('ix_monitoring_alerts_agentium_id', table_name='monitoring_alerts')
        print("Dropped monitoring_alerts agentium_id index")
    except Exception:
        pass
    
    print("✅ Downgrade completed")