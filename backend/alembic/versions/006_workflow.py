"""Add workflow_executions, workflow_subtasks tables and three new columns on tasks.

Revision ID: 006_workflow
Revises: 005_models
Create Date: 2026-03-17 00:00:00.000000

Changes
-------
NEW TABLES
  • workflow_executions  — top-level workflow record
  • workflow_subtasks    — one row per atomic sub-task

NEW COLUMNS on tasks (all nullable / with defaults → zero downtime)
  • workflow_id      VARCHAR(64)   NULL   — links a Task to a WorkflowExecution
  • context_data     JSON          NULL   — output written here on task completion
  • celery_task_id   VARCHAR(256)  NULL   — Celery task ID for scheduled tasks
"""

from alembic import op
import sqlalchemy as sa

revision = '006_workflow'
down_revision = '005_models'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── workflow_executions ────────────────────────────────────────────────
    op.create_table(
        'workflow_executions',
        sa.Column('id',               sa.String(36),  primary_key=True),
        sa.Column('workflow_id',      sa.String(64),  nullable=False, unique=True),
        sa.Column('original_message', sa.Text(),      nullable=False),
        sa.Column('status',           sa.String(32),  nullable=False, server_default='pending'),
        sa.Column('context_data',     sa.JSON(),      nullable=False, server_default='{}'),
        sa.Column('error',            sa.Text(),      nullable=True),
        sa.Column('created_by',       sa.String(128), nullable=True),
        sa.Column('created_at',       sa.DateTime(),  nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('updated_at',       sa.DateTime(),  nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('completed_at',     sa.DateTime(),  nullable=True),
    )
    op.create_index(
        'ix_workflow_executions_workflow_id',
        'workflow_executions', ['workflow_id'], unique=True,
    )
    op.create_index(
        'ix_workflow_executions_status',
        'workflow_executions', ['status'],
    )

    # ── workflow_subtasks ──────────────────────────────────────────────────
    op.create_table(
        'workflow_subtasks',
        sa.Column('id',                   sa.String(36),  primary_key=True),
        sa.Column('workflow_id',          sa.String(64),  nullable=False),
        sa.Column('step_index',           sa.Integer(),   nullable=False, server_default='0'),
        sa.Column('intent',               sa.String(128), nullable=False),
        sa.Column('params',               sa.JSON(),      nullable=False, server_default='{}'),
        sa.Column('depends_on',           sa.JSON(),      nullable=False, server_default='[]'),
        sa.Column('status',               sa.String(32),  nullable=False, server_default='pending'),
        sa.Column('result',               sa.JSON(),      nullable=True),
        sa.Column('error',                sa.Text(),      nullable=True),
        sa.Column('celery_task_id',       sa.String(256), nullable=True),
        sa.Column('schedule_offset_days', sa.Integer(),   nullable=False, server_default='0'),
        sa.Column('scheduled_for',        sa.DateTime(),  nullable=True),
        sa.Column('created_at',           sa.DateTime(),  nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('completed_at',         sa.DateTime(),  nullable=True),
        sa.ForeignKeyConstraint(
            ['workflow_id'],
            ['workflow_executions.workflow_id'],
            ondelete='CASCADE',
        ),
    )
    op.create_index(
        'ix_workflow_subtasks_workflow_id',
        'workflow_subtasks', ['workflow_id'],
    )
    op.create_index(
        'ix_workflow_subtasks_status',
        'workflow_subtasks', ['status'],
    )

    # ── New columns on tasks (all safe / non-breaking) ─────────────────────
    # ADD COLUMN IF NOT EXISTS prevents failures on re-runs or partial upgrades.
    op.execute(
        "ALTER TABLE tasks "
        "ADD COLUMN IF NOT EXISTS workflow_id VARCHAR(64) NULL"
    )
    op.execute(
        "ALTER TABLE tasks "
        "ADD COLUMN IF NOT EXISTS context_data JSON NULL"
    )
    op.execute(
        "ALTER TABLE tasks "
        "ADD COLUMN IF NOT EXISTS celery_task_id VARCHAR(256) NULL"
    )
    # Index workflow_id for fast look-ups
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_tasks_workflow_id "
        "ON tasks (workflow_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_tasks_workflow_id")
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS celery_task_id")
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS context_data")
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS workflow_id")

    op.drop_index('ix_workflow_subtasks_status',    table_name='workflow_subtasks')
    op.drop_index('ix_workflow_subtasks_workflow_id', table_name='workflow_subtasks')
    op.drop_table('workflow_subtasks')

    op.drop_index('ix_workflow_executions_status',     table_name='workflow_executions')
    op.drop_index('ix_workflow_executions_workflow_id', table_name='workflow_executions')
    op.drop_table('workflow_executions')