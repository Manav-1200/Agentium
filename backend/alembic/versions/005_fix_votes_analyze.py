"""Fix stale 'votes' table reference and db_maintenance ANALYZE list

Revision ID: 005_fix_votes_analyze
Revises: 004_migration
Create Date: 2026-03-01

The 'votes' table was referenced in db_maintenance ANALYZE calls but was
never created — the correct table is 'individual_votes'.
This migration:
  1. Documents the correct set of tables for ANALYZE (no-op in DB, for record)
  2. Drops any stale/orphaned 'votes' view or table if it somehow exists
  3. Creates a db_maintenance_config table so the ANALYZE table list is
     driven from the DB rather than hardcoded, preventing this class of bug.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

# revision identifiers
revision = '005_fix_votes_analyze'
down_revision = '004_migration'
branch_labels = None
depends_on = None


# Correct set of tables that should be ANALYZEd by db_maintenance
ANALYZE_TABLES = [
    'agents',
    'tasks',
    'subtasks',
    'individual_votes',   # ← correct table (was wrongly 'votes')
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

    print("🚀 Running migration 005_fix_votes_analyze...")

    # =========================================================================
    # 1. Safety: drop orphaned 'votes' table/view if it somehow exists
    # =========================================================================
    if 'votes' in existing_tables:
        print("  ⚠️  Stale 'votes' table found — dropping it.")
        op.execute("DROP TABLE IF EXISTS votes CASCADE")
        print("  ✅ Dropped stale 'votes' table")
    else:
        print("  ℹ️  No stale 'votes' table found (expected)")

    # Also drop any view named 'votes'
    op.execute("DROP VIEW IF EXISTS votes CASCADE")

    # =========================================================================
    # 2. Create db_maintenance_config table
    #    Stores the list of tables the maintenance service should ANALYZE,
    #    so it is data-driven rather than hardcoded in Python.
    # =========================================================================
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

    # =========================================================================
    # 3. Insert the correct ANALYZE table list as a config row
    # =========================================================================
    import json
    analyze_value = json.dumps(ANALYZE_TABLES)

    # Upsert — safe to run multiple times
    existing = conn.execute(text(
        "SELECT id FROM db_maintenance_config WHERE config_key = 'analyze_tables'"
    )).fetchone()

    if existing:
        conn.execute(text(
            "UPDATE db_maintenance_config "
            "SET config_value = :val, updated_at = NOW() "
            "WHERE config_key = 'analyze_tables'"
        ), {"val": analyze_value})
        print("  ✅ Updated analyze_tables config")
    else:
        conn.execute(text(
            "INSERT INTO db_maintenance_config (config_key, config_value, description) "
            "VALUES ('analyze_tables', :val, "
            "'JSON array of table names the db_maintenance service should ANALYZE')"
        ), {"val": analyze_value})
        print("  ✅ Inserted analyze_tables config")

    print("\n" + "=" * 60)
    print("✅ Migration 005_fix_votes_analyze completed!")
    print("=" * 60)
    print("Changes applied:")
    print("  • Dropped stale 'votes' table/view if present")
    print("  • Created db_maintenance_config table")
    print(f"  • Seeded correct ANALYZE table list ({len(ANALYZE_TABLES)} tables)")
    print("  • 'individual_votes' replaces the wrong 'votes' reference")
    print("=" * 60)
    print()
    print("ACTION REQUIRED — update backend/services/db_maintenance.py:")
    print("  Replace any hardcoded 'votes' entry in the ANALYZE table list")
    print("  with 'individual_votes', OR read the list from:")
    print("  db_maintenance_config WHERE config_key = 'analyze_tables'")


def downgrade():
    conn = op.get_bind()

    # Remove the config row
    conn.execute(text(
        "DELETE FROM db_maintenance_config WHERE config_key = 'analyze_tables'"
    ))

    # Drop the config table
    op.drop_table('db_maintenance_config')

    print("✅ Downgrade 005_fix_votes_analyze completed")