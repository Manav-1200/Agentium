"""task_schema_fixes

Revision ID: 004_task_schema_fixes
Revises: 003_user_preferences
Create Date: 2026-02-26

Fixes:
- Add missing `idempotency_key` column (VARCHAR 200, unique, nullable)
- Add missing `supervisor_id` column (VARCHAR 20, nullable)
- Fix `priority` column: integer → taskpriority enum
- Fix `task_type` column: varchar → tasktype enum
- Fix `created_by` column: varchar(36) → varchar(10)
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '004_task_schema_fixes'
down_revision = '003_user_preferences'
branch_labels = None
depends_on = None


def upgrade() -> None:

    # ── 1. Add missing columns ─────────────────────────────────────────────────

    op.add_column('tasks',
        sa.Column('idempotency_key', sa.String(200), unique=True, nullable=True)
    )
    op.create_index('ix_tasks_idempotency_key', 'tasks', ['idempotency_key'], unique=True)

    op.add_column('tasks',
        sa.Column('supervisor_id', sa.String(20), nullable=True)
    )

    # ── 2. Fix priority: integer → taskpriority enum ───────────────────────────
    #
    # Existing integer values came from the old schema.
    # We create the enum type first (if it doesn't already exist),
    # then cast the column using a USING expression.

    # Create the enum type if it doesn't exist yet
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'taskpriority') THEN
                CREATE TYPE taskpriority AS ENUM (
                    'sovereign', 'critical', 'high', 'normal', 'low', 'idle'
                );
            END IF;
        END$$;
    """)

    # Map old integer priorities to enum values, then cast
    op.execute("""
        ALTER TABLE tasks
        ALTER COLUMN priority DROP DEFAULT;
    """)

    op.execute("""
        ALTER TABLE tasks
        ALTER COLUMN priority TYPE taskpriority
        USING (
            CASE priority::text
                WHEN '0' THEN 'sovereign'
                WHEN '1' THEN 'normal'
                WHEN '2' THEN 'high'
                WHEN '3' THEN 'critical'
                ELSE 'normal'
            END
        )::taskpriority;
    """)

    op.execute("""
        ALTER TABLE tasks
        ALTER COLUMN priority SET DEFAULT 'normal'::taskpriority;
    """)

    # ── 3. Fix task_type: varchar → tasktype enum ──────────────────────────────

    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'tasktype') THEN
                CREATE TYPE tasktype AS ENUM (
                    'constitutional', 'system',
                    'one_time', 'recurring',
                    'execution', 'research', 'automation', 'analysis',
                    'communication', 'constitution_read',
                    'vector_maintenance', 'storage_dedupe', 'audit_archival',
                    'predictive_planning', 'constitution_refine',
                    'agent_health_scan', 'ethos_optimization',
                    'cache_optimization', 'idle_completed', 'idle_paused',
                    'preference_optimization'
                );
            END IF;
        END$$;
    """)

    op.execute("""
        ALTER TABLE tasks
        ALTER COLUMN task_type DROP DEFAULT;
    """)

    op.execute("""
        ALTER TABLE tasks
        ALTER COLUMN task_type TYPE tasktype
        USING (
            CASE
                WHEN task_type IN (
                    'constitutional', 'system', 'one_time', 'recurring',
                    'execution', 'research', 'automation', 'analysis',
                    'communication', 'constitution_read', 'vector_maintenance',
                    'storage_dedupe', 'audit_archival', 'predictive_planning',
                    'constitution_refine', 'agent_health_scan', 'ethos_optimization',
                    'cache_optimization', 'idle_completed', 'idle_paused',
                    'preference_optimization'
                ) THEN task_type::tasktype
                ELSE 'execution'::tasktype
            END
        );
    """)

    op.execute("""
        ALTER TABLE tasks
        ALTER COLUMN task_type SET DEFAULT 'execution'::tasktype;
    """)

    # ── 4. Fix created_by: varchar(36) → varchar(10) ───────────────────────────
    #
    # Truncate any values longer than 10 chars to avoid constraint violations.

    op.execute("""
        UPDATE tasks SET created_by = LEFT(created_by, 10)
        WHERE LENGTH(created_by) > 10;
    """)

    op.execute("""
        ALTER TABLE tasks
        ALTER COLUMN created_by TYPE VARCHAR(10);
    """)


def downgrade() -> None:

    # Reverse created_by back to varchar(36)
    op.execute("ALTER TABLE tasks ALTER COLUMN created_by TYPE VARCHAR(36);")

    # Reverse task_type back to varchar
    op.execute("""
        ALTER TABLE tasks
        ALTER COLUMN task_type TYPE VARCHAR(50)
        USING task_type::text;
    """)
    op.execute("ALTER TABLE tasks ALTER COLUMN task_type SET DEFAULT 'execution';")

    # Reverse priority back to integer
    op.execute("""
        ALTER TABLE tasks
        ALTER COLUMN priority TYPE INTEGER
        USING (
            CASE priority::text
                WHEN 'sovereign' THEN 0
                WHEN 'normal'    THEN 1
                WHEN 'high'      THEN 2
                WHEN 'critical'  THEN 3
                WHEN 'low'       THEN 1
                WHEN 'idle'      THEN 1
                ELSE 1
            END
        );
    """)
    op.execute("ALTER TABLE tasks ALTER COLUMN priority SET DEFAULT 1;")

    # Remove added columns
    op.drop_index('ix_tasks_idempotency_key', table_name='tasks')
    op.drop_column('tasks', 'idempotency_key')
    op.drop_column('tasks', 'supervisor_id')