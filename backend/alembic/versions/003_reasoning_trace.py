"""Reasoning Trace Tables

Revision ID: 003_reasoning_trace
Revises: 002_migration
Create Date: 2026-03-03

"""

import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = '003_reasoning_trace'
down_revision = '002_migration'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = set(inspector.get_table_names())

    print("🚀 Starting migration 003_reasoning_trace...")

    # =========================================================================
    # 1. reasoning_traces
    # =========================================================================
    if 'reasoning_traces' not in existing_tables:
        op.create_table(
            'reasoning_traces',
            # ── BaseEntity ────────────────────────────────────────────────────
            sa.Column('id',          sa.String(36),  primary_key=True),
            sa.Column('agentium_id', sa.String(20),  unique=True, nullable=False),
            sa.Column('is_active',   sa.Boolean(),   nullable=False, server_default='true'),
            sa.Column('created_at',  sa.DateTime(),  nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at',  sa.DateTime(),  nullable=False, server_default=sa.func.now()),
            sa.Column('deleted_at',  sa.DateTime(),  nullable=True),
            # ── Identity ──────────────────────────────────────────────────────
            sa.Column('trace_id',    sa.String(64),  nullable=False),
            sa.Column('task_id',     sa.String(64),  nullable=False),
            sa.Column('agent_id',    sa.String(32),  nullable=False),
            sa.Column('agent_tier',  sa.Integer(),   nullable=False, server_default='3'),
            sa.Column('incarnation', sa.Integer(),   nullable=False, server_default='1'),
            # ── Goal ──────────────────────────────────────────────────────────
            sa.Column('goal',          sa.Text(), nullable=False),
            sa.Column('goal_restated', sa.Text(), nullable=True),
            # ── Plan & context ────────────────────────────────────────────────
            sa.Column('plan',            sa.JSON(), nullable=True),   # List[str]
            sa.Column('skills_used',     sa.JSON(), nullable=True),   # List[str]
            sa.Column('context_summary', sa.Text(), nullable=True),
            # ── Phase & outcome ───────────────────────────────────────────────
            sa.Column('current_phase',     sa.String(32), nullable=False,
                      server_default='goal_interpretation'),
            sa.Column('final_outcome',     sa.String(16), nullable=True),   # success | failure
            sa.Column('failure_reason',    sa.Text(),     nullable=True),
            sa.Column('validation_passed', sa.Boolean(),  nullable=True),
            sa.Column('validation_notes',  sa.Text(),     nullable=True),
            # ── Timing & tokens ───────────────────────────────────────────────
            sa.Column('total_tokens',      sa.Integer(), nullable=False, server_default='0'),
            sa.Column('total_duration_ms', sa.Float(),   nullable=False, server_default='0.0'),
            sa.Column('started_at',        sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
            sa.Column('completed_at',      sa.DateTime(), nullable=True),
        )
        op.create_index('ix_reasoning_traces_trace_id',   'reasoning_traces', ['trace_id'],       unique=True)
        op.create_index('ix_reasoning_traces_task_id',    'reasoning_traces', ['task_id'])
        op.create_index('ix_reasoning_traces_agent_id',   'reasoning_traces', ['agent_id'])
        op.create_index('ix_reasoning_traces_outcome',    'reasoning_traces', ['final_outcome'])
        op.create_index('ix_reasoning_traces_phase',      'reasoning_traces', ['current_phase'])
        op.create_index('ix_reasoning_traces_created_at', 'reasoning_traces', ['created_at'])
        op.create_index('ix_reasoning_traces_validation', 'reasoning_traces', ['validation_passed'])
        print("  ✅ Created reasoning_traces table")
    else:
        print("  ℹ️  reasoning_traces already exists")

    # =========================================================================
    # 2. reasoning_steps
    # =========================================================================
    if 'reasoning_steps' not in existing_tables:
        op.create_table(
            'reasoning_steps',
            # ── BaseEntity ────────────────────────────────────────────────────
            sa.Column('id',          sa.String(36), primary_key=True),
            sa.Column('agentium_id', sa.String(20), unique=True, nullable=False),
            sa.Column('is_active',   sa.Boolean(),  nullable=False, server_default='true'),
            sa.Column('created_at',  sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at',  sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('deleted_at',  sa.DateTime(), nullable=True),
            # ── Parent ────────────────────────────────────────────────────────
            sa.Column('trace_id',    sa.String(64),
                      sa.ForeignKey('reasoning_traces.trace_id', ondelete='CASCADE'),
                      nullable=False),
            # ── Identity ──────────────────────────────────────────────────────
            sa.Column('step_id',   sa.String(80), nullable=False),
            sa.Column('phase',     sa.String(32), nullable=False),
            sa.Column('sequence',  sa.Integer(),  nullable=False),
            # ── Content ───────────────────────────────────────────────────────
            sa.Column('description',  sa.Text(),  nullable=False),
            sa.Column('rationale',    sa.Text(),  nullable=False),
            sa.Column('alternatives', sa.JSON(),  nullable=True),   # List[str]
            sa.Column('inputs',       sa.JSON(),  nullable=True),
            sa.Column('outputs',      sa.JSON(),  nullable=True),
            # ── Outcome ───────────────────────────────────────────────────────
            sa.Column('outcome',      sa.String(16), nullable=False, server_default='pending'),
            sa.Column('error',        sa.Text(),     nullable=True),
            sa.Column('tokens_used',  sa.Integer(),  nullable=False, server_default='0'),
            sa.Column('duration_ms',  sa.Float(),    nullable=False, server_default='0.0'),
            sa.Column('started_at',   sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
        )
        op.create_index('ix_reasoning_steps_step_id',           'reasoning_steps', ['step_id'],              unique=True)
        op.create_index('ix_reasoning_steps_trace_id',          'reasoning_steps', ['trace_id'])
        op.create_index('ix_reasoning_steps_phase',             'reasoning_steps', ['phase'])
        op.create_index('ix_reasoning_steps_outcome',           'reasoning_steps', ['outcome'])
        op.create_index('ix_reasoning_steps_trace_id_sequence', 'reasoning_steps', ['trace_id', 'sequence'])
        print("  ✅ Created reasoning_steps table")
    else:
        print("  ℹ️  reasoning_steps already exists")

    # =========================================================================
    # 3. tasks.latest_trace_id — soft shortcut, no hard FK so task rows
    #    can exist before any trace is produced
    # =========================================================================
    task_columns = {col['name'] for col in inspector.get_columns('tasks')}
    if 'latest_trace_id' not in task_columns:
        op.add_column('tasks', sa.Column('latest_trace_id', sa.String(64), nullable=True))
        print("  ✅ Added tasks.latest_trace_id")
    else:
        print("  ℹ️  tasks.latest_trace_id already exists")

    # =========================================================================
    # 4. Extend db_maintenance_config ANALYZE list
    # =========================================================================
    try:
        row = conn.execute(text(
            "SELECT config_value FROM db_maintenance_config "
            "WHERE config_key = 'analyze_tables'"
        )).fetchone()

        if row:
            current = json.loads(row[0])
            added = []
            for tbl in ('reasoning_traces', 'reasoning_steps'):
                if tbl not in current:
                    current.append(tbl)
                    added.append(tbl)
            if added:
                conn.execute(text(
                    "UPDATE db_maintenance_config "
                    "SET config_value = :val, updated_at = NOW() "
                    "WHERE config_key = 'analyze_tables'"
                ), {"val": json.dumps(current)})
                print(f"  ✅ Extended db_maintenance_config ANALYZE list: added {added}")
            else:
                print("  ℹ️  db_maintenance_config ANALYZE list already up to date")
        else:
            print("  ℹ️  db_maintenance_config row not found — skipping ANALYZE update")
    except Exception as exc:
        # Non-fatal: table may not exist on very fresh installs
        print(f"  ℹ️  Could not update db_maintenance_config: {exc}")

    print("\n" + "=" * 70)
    print("✅ Migration 003_reasoning_trace completed successfully!")
    print("=" * 70)
    print("Changes applied:")
    print("  • reasoning_traces  — full 5-phase execution trace per task/agent")
    print("  • reasoning_steps   — per-decision record (rationale, alternatives, outcome)")
    print("  • tasks.latest_trace_id — shortcut column for dashboard queries")
    print("  • db_maintenance_config ANALYZE list extended")
    print("=" * 70)


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    print("🔄 Starting downgrade of 003_reasoning_trace...")

    # ── tasks.latest_trace_id ─────────────────────────────────────────────────
    task_columns = {col['name'] for col in inspector.get_columns('tasks')}
    if 'latest_trace_id' in task_columns:
        op.drop_column('tasks', 'latest_trace_id')
        print("  ✅ Dropped tasks.latest_trace_id")

    # ── reasoning_steps (FK child — must go before parent) ───────────────────
    existing_tables = set(inspector.get_table_names())
    if 'reasoning_steps' in existing_tables:
        for idx in [
            'ix_reasoning_steps_trace_id_sequence',
            'ix_reasoning_steps_outcome',
            'ix_reasoning_steps_phase',
            'ix_reasoning_steps_trace_id',
            'ix_reasoning_steps_step_id',
        ]:
            try:
                op.drop_index(idx, table_name='reasoning_steps')
            except Exception:
                pass
        op.drop_table('reasoning_steps')
        print("  ✅ Dropped reasoning_steps")

    # ── reasoning_traces ──────────────────────────────────────────────────────
    if 'reasoning_traces' in existing_tables:
        for idx in [
            'ix_reasoning_traces_validation',
            'ix_reasoning_traces_created_at',
            'ix_reasoning_traces_phase',
            'ix_reasoning_traces_outcome',
            'ix_reasoning_traces_agent_id',
            'ix_reasoning_traces_task_id',
            'ix_reasoning_traces_trace_id',
        ]:
            try:
                op.drop_index(idx, table_name='reasoning_traces')
            except Exception:
                pass
        op.drop_table('reasoning_traces')
        print("  ✅ Dropped reasoning_traces")

    # ── Restore db_maintenance_config ANALYZE list ────────────────────────────
    try:
        row = conn.execute(text(
            "SELECT config_value FROM db_maintenance_config "
            "WHERE config_key = 'analyze_tables'"
        )).fetchone()
        if row:
            current = json.loads(row[0])
            restored = [t for t in current
                        if t not in ('reasoning_traces', 'reasoning_steps')]
            conn.execute(text(
                "UPDATE db_maintenance_config "
                "SET config_value = :val, updated_at = NOW() "
                "WHERE config_key = 'analyze_tables'"
            ), {"val": json.dumps(restored)})
            print("  ✅ Restored db_maintenance_config ANALYZE list")
    except Exception as exc:
        print(f"  ℹ️  Could not restore db_maintenance_config: {exc}")

    print("\n✅ Downgrade 003_reasoning_trace completed")