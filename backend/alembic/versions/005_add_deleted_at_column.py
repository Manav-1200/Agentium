"""Add deleted_at column to all tables inheriting from BaseEntity.

Revision ID: 005_add_deleted_at_column
Revises: 004_add_missing_agent_columns
Create Date: 2026-02-21 02:43:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '005_add_deleted_at_column'
down_revision = '004_add_missing_agent_columns'
branch_labels = None
depends_on = None


def upgrade():
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Only tables that exist BEFORE migration 006 runs
    # task_audit_logs, task_events, task_deliberations, voting_records are created in 006
    tables = [
        'users', 'user_model_configs', 'ethos', 'agents', 
        'scheduled_tasks', 'scheduled_task_executions', 'constitutions', 
        'tasks', 'subtasks', 'amendment_votings', 'individual_votes', 
        'audit_logs', 'channels', 'system_settings', 'model_usage_logs', 
        'conversations', 'chat_messages', 'agent_health_reports', 
        'violation_reports', 'task_verifications', 'performance_metrics', 
        'monitoring_alerts', 'critique_reviews',
        # These are created in 002_add_missing_tables
        'critic_agents',
        # Tool management tables from 6_1
        'tool_staging', 'tool_marketplace_listings', 'tool_versions',
        'tool_usage_logs',
        # Constitution/audit tables from 001/002
        'constitution_violations', 'session_logs', 'health_checks',
    ]
    
    for table in tables:
        try:
            columns = [c['name'] for c in inspector.get_columns(table)]
            if 'deleted_at' not in columns:
                op.add_column(table, sa.Column('deleted_at', sa.DateTime(), nullable=True))
        except Exception as e:
            # Table might not exist, skip silently
            print(f"Skipping {table}: {e}")
            continue


def downgrade():
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    
    tables = [
        'users', 'user_model_configs', 'ethos', 'agents', 
        'scheduled_tasks', 'scheduled_task_executions', 'constitutions', 
        'tasks', 'subtasks', 'amendment_votings', 'individual_votes', 
        'audit_logs', 'channels', 'system_settings', 'model_usage_logs', 
        'conversations', 'chat_messages', 'agent_health_reports', 
        'violation_reports', 'task_verifications', 'performance_metrics', 
        'monitoring_alerts', 'critique_reviews',
        'critic_agents',
        'tool_staging', 'tool_marketplace_listings', 'tool_versions',
        'tool_usage_logs',
        'constitution_violations', 'session_logs', 'health_checks',
    ]
    
    for table in tables:
        try:
            columns = [c['name'] for c in inspector.get_columns(table)]
            if 'deleted_at' in columns:
                op.drop_column(table, 'deleted_at')
        except Exception:
            continue