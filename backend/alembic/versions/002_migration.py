"""Combined Migration 002–006

Revision ID: 002_migration
Revises: 001_schema
Create Date: 2026-03-02

Consolidates the following migrations into one idempotent file:
  002_ab_testing          — A/B testing framework tables
  003_skill_system        — Skills & skill_submissions tables
  004_migration           — BaseEntity fixes, schema corrections, backup utilities
  005_fix_votes_analyze   — Drop stale 'votes' ref, create db_maintenance_config
  006_fix_votes_updated_at_and_experiment_status
                          — individual_votes.updated_at + uppercase enum variants
"""

import json
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text
from sqlalchemy.dialects import postgresql

revision = '002_migration'
down_revision = '001_schema'
branch_labels = None
depends_on = None


# Tables the db_maintenance service should ANALYZE
ANALYZE_TABLES = [
    'agents',
    'tasks',
    'subtasks',
    'individual_votes',
    'voting_records',
    'amendment_votings',
    'task_deliberations',
    'monitoring_alerts',
    'constitutions',
    'skills',
    'skill_submissions',
    'experiments',
    'experiment_runs',
    'experiment_results',
]


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = set(inspector.get_table_names())

    print("🚀 Starting combined migration 002_migration (002–006)...")

    # =========================================================================
    # [002] ENUM TYPES for A/B testing
    # =========================================================================
    print("\n🔧 [002] Creating A/B testing enum types...")

    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'experiment_status') THEN
                CREATE TYPE experiment_status AS ENUM (
                    'draft', 'pending', 'running', 'completed', 'failed', 'cancelled'
                );
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'run_status') THEN
                CREATE TYPE run_status AS ENUM (
                    'pending', 'running', 'completed', 'failed'
                );
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'task_complexity') THEN
                CREATE TYPE task_complexity AS ENUM (
                    'simple', 'medium', 'complex'
                );
            END IF;
        END $$;
    """)

    # =========================================================================
    # [002] A/B TESTING TABLES
    # =========================================================================

    # ── experiments ──────────────────────────────────────────────────────────
    if 'experiments' not in existing_tables:
        op.create_table(
            'experiments',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('name', sa.String(200), nullable=False),
            sa.Column('description', sa.Text()),
            sa.Column('task_template', sa.Text(), nullable=False),
            sa.Column('system_prompt', sa.Text()),
            sa.Column('test_iterations', sa.Integer(), server_default='1'),
            sa.Column(
                'status',
                postgresql.ENUM(
                    'draft', 'pending', 'running', 'completed', 'failed', 'cancelled',
                    name='experiment_status', create_type=False
                ),
                server_default='draft'
            ),
            sa.Column('created_by', sa.String(50), server_default='sovereign'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('started_at', sa.DateTime()),
            sa.Column('completed_at', sa.DateTime()),
        )
        op.create_index('idx_experiments_status', 'experiments', ['status'])
        op.create_index('idx_experiments_created_at', 'experiments', ['created_at'])
        print("  ✅ Created experiments table")
    else:
        print("  ℹ️  experiments already exists")

    # ── experiment_runs ───────────────────────────────────────────────────────
    if 'experiment_runs' not in existing_tables:
        op.create_table(
            'experiment_runs',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('experiment_id', sa.String(36), sa.ForeignKey('experiments.id', ondelete='CASCADE')),
            sa.Column('config_id', sa.String(36), sa.ForeignKey('user_model_configs.id', ondelete='SET NULL'), nullable=True),
            sa.Column('model_name', sa.String(100)),
            sa.Column('iteration_number', sa.Integer(), server_default='1'),
            sa.Column(
                'status',
                postgresql.ENUM(
                    'pending', 'running', 'completed', 'failed',
                    name='run_status', create_type=False
                ),
                server_default='pending'
            ),
            sa.Column('output_text', sa.Text()),
            sa.Column('tokens_used', sa.Integer()),
            sa.Column('latency_ms', sa.Integer()),
            sa.Column('cost_usd', sa.Float()),
            sa.Column('critic_plan_score', sa.Float()),
            sa.Column('critic_code_score', sa.Float()),
            sa.Column('critic_output_score', sa.Float()),
            sa.Column('overall_quality_score', sa.Float()),
            sa.Column('critic_feedback', postgresql.JSON()),
            sa.Column('constitutional_violations', sa.Integer(), server_default='0'),
            sa.Column('started_at', sa.DateTime()),
            sa.Column('completed_at', sa.DateTime()),
            sa.Column('error_message', sa.Text()),
        )
        op.create_index('idx_experiment_runs_experiment_id', 'experiment_runs', ['experiment_id'])
        op.create_index('idx_experiment_runs_config_id', 'experiment_runs', ['config_id'])
        op.create_index('idx_experiment_runs_status', 'experiment_runs', ['status'])
        print("  ✅ Created experiment_runs table")
    else:
        print("  ℹ️  experiment_runs already exists")

    # ── experiment_results ────────────────────────────────────────────────────
    if 'experiment_results' not in existing_tables:
        op.create_table(
            'experiment_results',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('experiment_id', sa.String(36), sa.ForeignKey('experiments.id', ondelete='CASCADE')),
            sa.Column('winner_config_id', sa.String(36), sa.ForeignKey('user_model_configs.id', ondelete='SET NULL'), nullable=True),
            sa.Column('winner_model_name', sa.String(100)),
            sa.Column('selection_reason', sa.Text()),
            sa.Column('model_comparisons', postgresql.JSON()),
            sa.Column('statistical_significance', sa.Float()),
            sa.Column('recommended_for_similar', sa.Boolean(), server_default='false'),
            sa.Column('confidence_score', sa.Float()),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index('idx_experiment_results_experiment_id', 'experiment_results', ['experiment_id'])
        print("  ✅ Created experiment_results table")
    else:
        print("  ℹ️  experiment_results already exists")

    # ── model_performance_cache ───────────────────────────────────────────────
    if 'model_performance_cache' not in existing_tables:
        op.create_table(
            'model_performance_cache',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('task_category', sa.String(50)),
            sa.Column(
                'task_complexity',
                postgresql.ENUM(
                    'simple', 'medium', 'complex',
                    name='task_complexity', create_type=False
                ),
            ),
            sa.Column('best_config_id', sa.String(36), sa.ForeignKey('user_model_configs.id', ondelete='SET NULL'), nullable=True),
            sa.Column('best_model_name', sa.String(100)),
            sa.Column('avg_latency_ms', sa.Integer()),
            sa.Column('avg_cost_usd', sa.Float()),
            sa.Column('avg_quality_score', sa.Float()),
            sa.Column('success_rate', sa.Float()),
            sa.Column('derived_from_experiment_id', sa.String(36), sa.ForeignKey('experiments.id', ondelete='SET NULL'), nullable=True),
            sa.Column('sample_size', sa.Integer()),
            sa.Column('last_updated', sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index('idx_performance_cache_category', 'model_performance_cache', ['task_category'])
        op.create_index('idx_performance_cache_quality', 'model_performance_cache', ['avg_quality_score'])
        print("  ✅ Created model_performance_cache table")
    else:
        print("  ℹ️  model_performance_cache already exists")

    # =========================================================================
    # [003] SKILL SYSTEM TABLES
    # =========================================================================
    print("\n🔧 [003] Creating skill system tables...")

    if 'skills' not in existing_tables:
        op.create_table(
            'skills',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('agentium_id', sa.String(length=20), unique=True, nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
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
            sa.UniqueConstraint('skill_id'),
        )
        op.create_index('ix_skills_skill_id', 'skills', ['skill_id'], unique=True)
        op.create_index('ix_skills_agentium_id', 'skills', ['agentium_id'], unique=True)
        op.create_index('ix_skills_domain', 'skills', ['domain'])
        op.create_index('ix_skills_skill_type', 'skills', ['skill_type'])
        op.create_index('ix_skills_verification_status', 'skills', ['verification_status'])
        print("  ✅ Created skills table")
    else:
        print("  ℹ️  skills already exists")

    if 'skill_submissions' not in existing_tables:
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
            sa.UniqueConstraint('submission_id'),
        )
        op.create_index('ix_skill_submissions_status', 'skill_submissions', ['status'])
        print("  ✅ Created skill_submissions table")
    else:
        print("  ℹ️  skill_submissions already exists")

    # =========================================================================
    # [004] FIX tool_marketplace_listings — Add missing BaseEntity columns
    # =========================================================================
    print("\n🔧 [004] Checking tool_marketplace_listings schema...")

    existing_columns = {col['name'] for col in inspector.get_columns('tool_marketplace_listings')}

    if 'agentium_id' not in existing_columns:
        op.add_column('tool_marketplace_listings', sa.Column('agentium_id', sa.String(20), unique=True, nullable=True))
        op.create_index('ix_tool_marketplace_listings_agentium_id', 'tool_marketplace_listings', ['agentium_id'], unique=True)
        print("  ✅ Added agentium_id column")
    else:
        print("  ℹ️  agentium_id already exists")

    if 'is_active' not in existing_columns:
        op.add_column('tool_marketplace_listings', sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False))
        print("  ✅ Added is_active column")
    else:
        print("  ℹ️  is_active already exists")

    if 'created_at' not in existing_columns:
        op.add_column('tool_marketplace_listings', sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False))
        print("  ✅ Added created_at column")
    else:
        print("  ℹ️  created_at already exists")

    if 'updated_at' not in existing_columns:
        op.add_column('tool_marketplace_listings', sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False))
        print("  ✅ Added updated_at column")
    else:
        print("  ℹ️  updated_at already exists")

    if 'deleted_at' not in existing_columns:
        op.add_column('tool_marketplace_listings', sa.Column('deleted_at', sa.DateTime(), nullable=True))
        print("  ✅ Added deleted_at column")
    else:
        print("  ℹ️  deleted_at already exists")

    # Backfill agentium_id for existing rows
    null_count = conn.execute(text(
        "SELECT COUNT(*) FROM tool_marketplace_listings WHERE agentium_id IS NULL"
    )).scalar()
    if null_count > 0:
        op.execute("""
            UPDATE tool_marketplace_listings
            SET agentium_id = 'MKTL' || LPAD(id::text, 5, '0'),
                is_active   = COALESCE(is_active, true),
                created_at  = COALESCE(created_at, published_at, NOW()),
                updated_at  = COALESCE(updated_at, NOW())
            WHERE agentium_id IS NULL
        """)
        print(f"  ✅ Backfilled {null_count} rows in tool_marketplace_listings")

    # =========================================================================
    # [004] FIX monitoring_alerts.agentium_id — make nullable
    # =========================================================================
    print("\n🔧 [004] Checking monitoring_alerts schema...")

    ma_columns = {col['name']: col for col in inspector.get_columns('monitoring_alerts')}

    if 'agentium_id' in ma_columns:
        result = conn.execute(text("""
            SELECT is_nullable FROM information_schema.columns
            WHERE table_name = 'monitoring_alerts' AND column_name = 'agentium_id'
        """)).fetchone()
        if result and result[0] == 'NO':
            op.execute("ALTER TABLE monitoring_alerts ALTER COLUMN agentium_id DROP NOT NULL")
            print("  ✅ monitoring_alerts.agentium_id is now nullable")
        else:
            print("  ℹ️  monitoring_alerts.agentium_id already nullable")
    else:
        op.add_column('monitoring_alerts', sa.Column('agentium_id', sa.String(10), unique=True, nullable=True))
        existing_indexes = {idx['name'] for idx in inspector.get_indexes('monitoring_alerts')}
        if 'ix_monitoring_alerts_agentium_id' not in existing_indexes:
            op.create_index('ix_monitoring_alerts_agentium_id', 'monitoring_alerts', ['agentium_id'], unique=True)
        print("  ✅ Created monitoring_alerts.agentium_id as nullable")

    # =========================================================================
    # [004] Create PostgreSQL backup helper functions
    # =========================================================================
    print("\n🔧 [004] Creating backup helper functions...")

    op.execute("""
        CREATE OR REPLACE FUNCTION create_backup_sql()
        RETURNS text AS $$
        DECLARE
            result text := '';
            rec record;
        BEGIN
            FOR rec IN
                SELECT 'CREATE TABLE IF NOT EXISTS ' || tablename || ' (' ||
                    string_agg(
                        column_name || ' ' ||
                        CASE
                            WHEN data_type = 'character varying' AND character_maximum_length IS NOT NULL
                                THEN 'varchar(' || character_maximum_length || ')'
                            WHEN data_type = 'character varying'  THEN 'varchar'
                            WHEN data_type = 'integer'            THEN 'integer'
                            WHEN data_type = 'bigint'             THEN 'bigint'
                            WHEN data_type = 'boolean'            THEN 'boolean'
                            WHEN data_type = 'timestamp without time zone' THEN 'timestamp'
                            WHEN data_type = 'timestamp with time zone'    THEN 'timestamptz'
                            WHEN data_type = 'text'               THEN 'text'
                            WHEN data_type = 'json'               THEN 'json'
                            WHEN data_type = 'jsonb'              THEN 'jsonb'
                            WHEN data_type = 'uuid'               THEN 'uuid'
                            WHEN data_type = 'numeric'            THEN 'numeric'
                            WHEN data_type = 'double precision'   THEN 'float'
                            WHEN data_type = 'real'               THEN 'real'
                            ELSE data_type
                        END ||
                        CASE WHEN is_nullable = 'NO' THEN ' NOT NULL' ELSE '' END,
                        ', ' ORDER BY ordinal_position
                    ) || ');' AS ddl
                FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name NOT LIKE 'pg_%'
                AND table_name NOT LIKE 'sql_%'
                GROUP BY tablename
            LOOP
                result := result || rec.ddl || E'\n\n';
            END LOOP;
            result := result || '-- Backup generated at: ' || NOW()::text || E'\n';
            RETURN result;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION backup_table_to_json(table_name text)
        RETURNS json AS $$
        DECLARE
            result json;
            query  text;
        BEGIN
            query := 'SELECT json_agg(row_to_json(t)) FROM ' || quote_ident(table_name) || ' t';
            EXECUTE query INTO result;
            RETURN COALESCE(result, '[]'::json);
        END;
        $$ LANGUAGE plpgsql;
    """)
    print("  ✅ Created create_backup_sql() and backup_table_to_json() functions")

    # =========================================================================
    # [005] Drop stale 'votes' table/view if present
    # =========================================================================
    print("\n🔧 [005] Checking for stale 'votes' table/view...")

    # Re-fetch table list in case it changed
    existing_tables = set(inspect(conn).get_table_names())

    if 'votes' in existing_tables:
        op.execute("DROP TABLE IF EXISTS votes CASCADE")
        print("  ✅ Dropped stale 'votes' table")
    else:
        print("  ℹ️  No stale 'votes' table found (expected)")

    op.execute("DROP VIEW IF EXISTS votes CASCADE")

    # =========================================================================
    # [005] Create db_maintenance_config table & seed ANALYZE list
    # =========================================================================
    print("\n🔧 [005] Setting up db_maintenance_config...")

    existing_tables = set(inspect(conn).get_table_names())

    if 'db_maintenance_config' not in existing_tables:
        op.create_table(
            'db_maintenance_config',
            sa.Column('id', sa.Integer(), autoincrement=True, primary_key=True),
            sa.Column('config_key', sa.String(100), nullable=False, unique=True),
            sa.Column('config_value', sa.Text(), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        )
        print("  ✅ Created db_maintenance_config table")
    else:
        print("  ℹ️  db_maintenance_config already exists")

    analyze_value = json.dumps(ANALYZE_TABLES)
    existing_row = conn.execute(text(
        "SELECT id FROM db_maintenance_config WHERE config_key = 'analyze_tables'"
    )).fetchone()

    if existing_row:
        conn.execute(text(
            "UPDATE db_maintenance_config SET config_value = :val, updated_at = NOW() "
            "WHERE config_key = 'analyze_tables'"
        ), {"val": analyze_value})
        print("  ✅ Updated analyze_tables config")
    else:
        conn.execute(text(
            "INSERT INTO db_maintenance_config (config_key, config_value, description) "
            "VALUES ('analyze_tables', :val, "
            "'JSON array of table names the db_maintenance service should ANALYZE')"
        ), {"val": analyze_value})
        print("  ✅ Inserted analyze_tables config (individual_votes replaces stale 'votes')")

    # =========================================================================
    # [006] ADD individual_votes.updated_at
    # =========================================================================
    print("\n🔧 [006] Checking individual_votes.updated_at...")

    iv_columns = {col['name'] for col in inspector.get_columns('individual_votes')}

    if 'updated_at' not in iv_columns:
        op.add_column('individual_votes', sa.Column('updated_at', sa.DateTime(), nullable=True))
        conn.execute(text("UPDATE individual_votes SET updated_at = created_at WHERE updated_at IS NULL"))
        conn.execute(text("""
            ALTER TABLE individual_votes
                ALTER COLUMN updated_at SET NOT NULL,
                ALTER COLUMN updated_at SET DEFAULT NOW()
        """))
        print("  ✅ Added updated_at, backfilled from created_at, set NOT NULL + DEFAULT NOW()")
    else:
        print("  ℹ️  individual_votes.updated_at already exists")

    # =========================================================================
    # [006] ADD UPPERCASE VARIANTS TO experiment_status, run_status, task_complexity
    # =========================================================================
    print("\n🔧 [006] Adding uppercase enum variants...")

    def add_missing_enum_values(type_name: str, values: list) -> list:
        added = []
        for val in values:
            exists = conn.execute(text("""
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = :type_name AND e.enumlabel = :val
            """), {"type_name": type_name, "val": val}).fetchone()
            if not exists:
                conn.execute(text(f"ALTER TYPE {type_name} ADD VALUE '{val}'"))
                added.append(val)
        return added

    added = add_missing_enum_values(
        'experiment_status',
        ['DRAFT', 'PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED'],
    )
    print(f"  {'✅ experiment_status: added ' + str(added) if added else 'ℹ️  experiment_status: uppercase variants already present'}")

    added = add_missing_enum_values('run_status', ['PENDING', 'RUNNING', 'COMPLETED', 'FAILED'])
    print(f"  {'✅ run_status: added ' + str(added) if added else 'ℹ️  run_status: uppercase variants already present'}")

    added = add_missing_enum_values('task_complexity', ['SIMPLE', 'MEDIUM', 'COMPLEX'])
    print(f"  {'✅ task_complexity: added ' + str(added) if added else 'ℹ️  task_complexity: uppercase variants already present'}")

    print("\n" + "=" * 70)
    print("✅ Combined migration 002_migration completed successfully!")
    print("=" * 70)
    print("Changes applied:")
    print("  • [002] experiment_status / run_status / task_complexity enums created")
    print("  • [002] experiments, experiment_runs, experiment_results, model_performance_cache tables")
    print("  • [003] skills, skill_submissions tables")
    print("  • [004] tool_marketplace_listings: BaseEntity columns added")
    print("  • [004] monitoring_alerts.agentium_id made nullable")
    print("  • [004] PostgreSQL backup functions created")
    print("  • [005] Stale 'votes' table/view dropped if present")
    print("  • [005] db_maintenance_config table created & seeded")
    print("  • [006] individual_votes.updated_at added & backfilled")
    print("  • [006] Uppercase variants added to experiment_status, run_status, task_complexity")
    print("=" * 70)
    print()
    print("ACTION REQUIRED — update backend/services/db_maintenance.py:")
    print("  Replace any hardcoded 'votes' entry in the ANALYZE table list")
    print("  with 'individual_votes', OR read the list from:")
    print("  db_maintenance_config WHERE config_key = 'analyze_tables'")


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    print("🔄 Starting downgrade of 002_migration...")

    # =========================================================================
    # [006] Drop individual_votes.updated_at
    #       NOTE: Uppercase enum values CANNOT be removed in PostgreSQL.
    # =========================================================================
    iv_columns = {col['name'] for col in inspector.get_columns('individual_votes')}
    if 'updated_at' in iv_columns:
        op.drop_column('individual_votes', 'updated_at')
        print("  ✅ Dropped individual_votes.updated_at")

    print("  ⚠️  NOTE: Uppercase enum variants for experiment_status, run_status,")
    print("      and task_complexity cannot be removed (PostgreSQL limitation).")

    # =========================================================================
    # [005] Remove db_maintenance_config
    # =========================================================================
    conn.execute(text("DELETE FROM db_maintenance_config WHERE config_key = 'analyze_tables'"))
    existing_tables = set(inspector.get_table_names())
    if 'db_maintenance_config' in existing_tables:
        op.drop_table('db_maintenance_config')
        print("  ✅ Dropped db_maintenance_config")

    # =========================================================================
    # [004] Restore monitoring_alerts.agentium_id to NOT NULL (if safe)
    # =========================================================================
    try:
        null_count = conn.execute(text(
            "SELECT COUNT(*) FROM monitoring_alerts WHERE agentium_id IS NULL"
        )).scalar()
        if null_count == 0:
            op.execute("ALTER TABLE monitoring_alerts ALTER COLUMN agentium_id SET NOT NULL")
            print("  ✅ Restored monitoring_alerts.agentium_id to NOT NULL")
        else:
            print(f"  ℹ️  Cannot restore NOT NULL: {null_count} rows have NULL agentium_id")
    except Exception as e:
        print(f"  Note: could not restore monitoring_alerts constraint: {e}")

    # [004] Remove BaseEntity columns from tool_marketplace_listings
    try:
        op.drop_index('ix_tool_marketplace_listings_agentium_id', table_name='tool_marketplace_listings')
    except Exception:
        pass
    for col in ['deleted_at', 'updated_at', 'created_at', 'is_active', 'agentium_id']:
        try:
            op.drop_column('tool_marketplace_listings', col)
            print(f"  ✅ Dropped tool_marketplace_listings.{col}")
        except Exception as e:
            print(f"  Note: could not drop {col}: {e}")

    # [004] Drop backup functions
    op.execute("DROP FUNCTION IF EXISTS create_backup_sql()")
    op.execute("DROP FUNCTION IF EXISTS backup_table_to_json(text)")
    print("  ✅ Dropped backup helper functions")

    # =========================================================================
    # [003] Drop skill system tables
    # =========================================================================
    try:
        op.drop_index('ix_skill_submissions_status', table_name='skill_submissions')
        op.drop_table('skill_submissions')
        print("  ✅ Dropped skill_submissions")
    except Exception as e:
        print(f"  Note: {e}")

    for idx in ['ix_skills_verification_status', 'ix_skills_skill_type', 'ix_skills_domain',
                'ix_skills_agentium_id', 'ix_skills_skill_id']:
        try:
            op.drop_index(idx, table_name='skills')
        except Exception:
            pass
    try:
        op.drop_table('skills')
        print("  ✅ Dropped skills")
    except Exception as e:
        print(f"  Note: {e}")

    # =========================================================================
    # [002] Drop A/B testing tables and enum types
    # =========================================================================
    for table in ['model_performance_cache', 'experiment_results', 'experiment_runs', 'experiments']:
        try:
            op.drop_table(table)
            print(f"  ✅ Dropped {table}")
        except Exception as e:
            print(f"  Note: could not drop {table}: {e}")

    for enum_type in ['task_complexity', 'run_status', 'experiment_status']:
        op.execute(f"DROP TYPE IF EXISTS {enum_type} CASCADE")
        print(f"  ✅ Dropped enum {enum_type}")

    print("\n✅ Downgrade 002_migration completed")