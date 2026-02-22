"""Agentium Complete Schema Migration (consolidated)

This is the single canonical migration that replaces all previous migrations
(001 through 004).  It creates the complete database schema in one go,
including remote-execution tables and unified-inbox alignment columns.

Revision ID: 001_schema
Revises:
Create Date: 2026-02-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text
from sqlalchemy.dialects import postgresql

revision = '001_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # =========================================================================
    # ENUM TYPES
    # =========================================================================
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'taskstatus') THEN
                CREATE TYPE taskstatus AS ENUM (
                    'pending', 'deliberating', 'approved', 'rejected', 'delegating',
                    'assigned', 'in_progress', 'review', 'completed', 'failed', 'cancelled',
                    'idle_pending', 'idle_running', 'idle_paused', 'idle_completed',
                    'PENDING', 'DELIBERATING', 'APPROVED', 'REJECTED', 'DELEGATING',
                    'ASSIGNED', 'IN_PROGRESS', 'REVIEW', 'COMPLETED', 'FAILED',
                    'CANCELLED', 'IDLE_PENDING', 'IDLE_RUNNING', 'IDLE_PAUSED',
                    'IDLE_COMPLETED', 'ESCALATED'
                );
            END IF;
        END $$;
    """)

    # =========================================================================
    # 1. USERS
    # =========================================================================
    if 'users' not in existing_tables:
        op.create_table(
            'users',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('username', sa.String(50), unique=True, nullable=False),
            sa.Column('email', sa.String(100), unique=True, nullable=False),
            sa.Column('hashed_password', sa.String(255), nullable=False),
            sa.Column('is_active', sa.Boolean(), server_default='true'),
            sa.Column('is_admin', sa.Boolean(), server_default='false'),
            sa.Column('is_pending', sa.Boolean(), server_default='true', nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
        )

    # =========================================================================
    # 2. USER MODEL CONFIGS
    # =========================================================================
    if 'user_model_configs' not in existing_tables:
        op.create_table(
            'user_model_configs',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('agentium_id', sa.String(20), unique=True, nullable=True),
            sa.Column('user_id', sa.String(36), nullable=True),
            sa.Column('config_name', sa.String(100), nullable=False),
            sa.Column('provider', sa.String(30), nullable=False),
            sa.Column('provider_name', sa.String(50), nullable=True),
            sa.Column('default_model', sa.String(100), nullable=False),
            sa.Column('available_models', sa.JSON(), nullable=True),
            sa.Column('model_family', sa.String(50), nullable=True),
            sa.Column('api_key_encrypted', sa.Text(), nullable=True),
            sa.Column('api_key_masked', sa.String(10), nullable=True),
            sa.Column('api_base_url', sa.String(500), nullable=True),
            sa.Column('azure_endpoint', sa.String(500), nullable=True),
            sa.Column('azure_deployment', sa.String(100), nullable=True),
            sa.Column('local_server_url', sa.String(500), nullable=True),
            sa.Column('max_tokens', sa.Integer(), server_default='4000'),
            sa.Column('temperature', sa.Float(), server_default='0.7'),
            sa.Column('top_p', sa.Float(), server_default='1.0'),
            sa.Column('timeout_seconds', sa.Integer(), server_default='60'),
            sa.Column('rate_limit', sa.Integer(), nullable=True),
            sa.Column('status', sa.String(20), server_default='TESTING'),
            sa.Column('last_error', sa.Text(), nullable=True),
            sa.Column('last_tested_at', sa.DateTime(), nullable=True),
            sa.Column('last_used_at', sa.DateTime(), nullable=True),
            sa.Column('is_default', sa.Boolean(), server_default='false'),
            sa.Column('is_active', sa.Boolean(), server_default='true'),
            sa.Column('total_requests', sa.Integer(), server_default='0'),
            sa.Column('total_tokens', sa.Integer(), server_default='0'),
            sa.Column('estimated_cost_usd', sa.Float(), server_default='0.0'),
            sa.Column('extra_params', sa.JSON(), nullable=True),
            sa.Column('priority', sa.Integer(), server_default='999', nullable=False),
            sa.Column('failure_count', sa.Integer(), server_default='0', nullable=False),
            sa.Column('last_failure_at', sa.DateTime(), nullable=True),
            sa.Column('cooldown_until', sa.DateTime(), nullable=True),
            sa.Column('monthly_budget_usd', sa.Float(), server_default='0.0', nullable=False),
            sa.Column('current_spend_usd', sa.Float(), server_default='0.0', nullable=False),
            sa.Column('last_spend_reset', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
        )
        op.create_index('ix_user_model_configs_agentium_id', 'user_model_configs', ['agentium_id'],
                        unique=True, postgresql_where=sa.text("agentium_id IS NOT NULL"))

    # =========================================================================
    # 3. ETHOS
    # =========================================================================
    if 'ethos' not in existing_tables:
        op.create_table(
            'ethos',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('agentium_id', sa.String(20), unique=True, nullable=True),
            sa.Column('agent_type', sa.String(20), nullable=False),
            sa.Column('mission_statement', sa.Text(), nullable=False),
            sa.Column('core_values', sa.Text(), nullable=False),
            sa.Column('behavioral_rules', sa.Text(), nullable=False),
            sa.Column('restrictions', sa.Text(), nullable=False),
            sa.Column('capabilities', sa.Text(), nullable=False),
            sa.Column('current_objective', sa.Text(), nullable=True),
            sa.Column('active_plan', sa.Text(), nullable=True),
            sa.Column('constitutional_references', sa.JSON(), nullable=True),
            sa.Column('task_progress_markers', sa.JSON(), nullable=True),
            sa.Column('reasoning_artifacts', sa.JSON(), nullable=True),
            sa.Column('outcome_summary', sa.Text(), nullable=True),
            sa.Column('lessons_learned', sa.Text(), nullable=True),
            sa.Column('created_by_agentium_id', sa.String(10), nullable=False),
            sa.Column('version', sa.Integer(), server_default='1'),
            sa.Column('agent_id', sa.String(36), nullable=False),
            sa.Column('verified_by_agentium_id', sa.String(10), nullable=True),
            sa.Column('verified_at', sa.DateTime(), nullable=True),
            sa.Column('is_verified', sa.Boolean(), server_default='false'),
            sa.Column('last_updated_by_agent', sa.Boolean(), server_default='false'),
            sa.Column('is_active', sa.Boolean(), server_default='true'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
        )

    # =========================================================================
    # 4. AGENTS
    # =========================================================================
    if 'agents' not in existing_tables:
        op.create_table(
            'agents',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('agentium_id', sa.String(20), unique=True, nullable=False),
            sa.Column('agent_type', sa.String(20), nullable=False),
            sa.Column('name', sa.String(100), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('custom_capabilities', sa.Text(), nullable=True),
            sa.Column('incarnation_number', sa.Integer(), server_default='1'),
            sa.Column('parent_id', sa.String(36), sa.ForeignKey('agents.id'), nullable=True),
            sa.Column('status', sa.String(20), server_default='initializing'),
            sa.Column('terminated_at', sa.DateTime(), nullable=True),
            sa.Column('termination_reason', sa.Text(), nullable=True),
            sa.Column('preferred_config_id', sa.String(36), sa.ForeignKey('user_model_configs.id'), nullable=True),
            sa.Column('system_prompt_override', sa.Text(), nullable=True),
            sa.Column('ethos_id', sa.String(36), sa.ForeignKey('ethos.id'), nullable=True),
            sa.Column('constitution_version', sa.String(10), nullable=True),
            sa.Column('created_by_agentium_id', sa.String(10), nullable=True),
            sa.Column('spawned_at_task_count', sa.Integer(), server_default='0'),
            sa.Column('tasks_completed', sa.Integer(), server_default='0'),
            sa.Column('tasks_failed', sa.Integer(), server_default='0'),
            sa.Column('current_task_id', sa.String(36), nullable=True),
            sa.Column('is_persistent', sa.Boolean(), server_default='false'),
            sa.Column('idle_mode_enabled', sa.Boolean(), server_default='false'),
            sa.Column('last_idle_action_at', sa.DateTime(), nullable=True),
            sa.Column('idle_task_count', sa.Integer(), server_default='0'),
            sa.Column('idle_tokens_saved', sa.Integer(), server_default='0'),
            sa.Column('current_idle_task_id', sa.String(36), nullable=True),
            sa.Column('persistent_role', sa.String(50), nullable=True),
            sa.Column('last_constitution_read_at', sa.DateTime(), nullable=True),
            sa.Column('constitution_read_count', sa.Integer(), server_default='0'),
            sa.Column('ethos_last_read_at', sa.DateTime(), nullable=True),
            sa.Column('ethos_action_pending', sa.Boolean(), server_default='false'),
            sa.Column('is_active', sa.Boolean(), server_default='true'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
        )
        op.create_index('idx_agent_type_status', 'agents', ['agent_type', 'status'])
        op.create_index('idx_parent_id', 'agents', ['parent_id'])
        op.create_index('idx_agents_is_persistent', 'agents', ['is_persistent'])
        op.create_index('idx_agents_last_idle', 'agents', ['last_idle_action_at'])

    # =========================================================================
    # 5. AGENT SUBTYPE TABLES
    # =========================================================================
    if 'head_of_council' not in existing_tables:
        op.create_table(
            'head_of_council',
            sa.Column('id', sa.String(36), sa.ForeignKey('agents.id'), primary_key=True),
            sa.Column('emergency_override_used_at', sa.DateTime(), nullable=True),
            sa.Column('last_constitution_update', sa.DateTime(), nullable=True),
        )

    if 'council_members' not in existing_tables:
        op.create_table(
            'council_members',
            sa.Column('id', sa.String(36), sa.ForeignKey('agents.id'), primary_key=True),
            sa.Column('specialization', sa.String(50), nullable=True),
            sa.Column('votes_participated', sa.Integer(), server_default='0'),
            sa.Column('votes_abstained', sa.Integer(), server_default='0'),
        )

    if 'lead_agents' not in existing_tables:
        op.create_table(
            'lead_agents',
            sa.Column('id', sa.String(36), sa.ForeignKey('agents.id'), primary_key=True),
            sa.Column('team_size', sa.Integer(), server_default='0'),
            sa.Column('max_team_size', sa.Integer(), server_default='10'),
            sa.Column('department', sa.String(50), nullable=True),
            sa.Column('spawn_threshold', sa.Integer(), server_default='5'),
        )

    if 'task_agents' not in existing_tables:
        op.create_table(
            'task_agents',
            sa.Column('id', sa.String(36), sa.ForeignKey('agents.id'), primary_key=True),
            sa.Column('assigned_tools', sa.Text(), nullable=True),
            sa.Column('execution_timeout', sa.Integer(), server_default='300'),
            sa.Column('sandbox_enabled', sa.Boolean(), server_default='true'),
        )

    if 'critic_agents' not in existing_tables:
        op.create_table(
            'critic_agents',
            sa.Column('id', sa.String(36), sa.ForeignKey('agents.id'), primary_key=True),
            sa.Column('critic_specialty', sa.String(20), nullable=False),
            sa.Column('reviews_completed', sa.Integer(), server_default='0'),
            sa.Column('vetoes_issued', sa.Integer(), server_default='0'),
            sa.Column('escalations_issued', sa.Integer(), server_default='0'),
            sa.Column('passes_issued', sa.Integer(), server_default='0'),
            sa.Column('avg_review_time_ms', sa.Float(), server_default='0.0'),
            sa.Column('preferred_review_model', sa.String(100), nullable=True),
        )

    # =========================================================================
    # 6. CONSTITUTIONS
    # =========================================================================
    if 'constitutions' not in existing_tables:
        op.create_table(
            'constitutions',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('agentium_id', sa.String(20), unique=True, nullable=False),
            sa.Column('version', sa.String(10), unique=True, nullable=False),
            sa.Column('version_number', sa.Integer(), unique=True, nullable=False),
            sa.Column('document_type', sa.String(20), nullable=False),
            sa.Column('preamble', sa.Text(), nullable=True),
            sa.Column('articles', sa.Text(), nullable=False),
            sa.Column('prohibited_actions', sa.Text(), nullable=False),
            sa.Column('sovereign_preferences', sa.Text(), nullable=False),
            sa.Column('changelog', sa.Text(), nullable=True),
            sa.Column('created_by_agentium_id', sa.String(10), nullable=False),
            sa.Column('amendment_of', sa.String(36), sa.ForeignKey('constitutions.id'), nullable=True),
            sa.Column('replaces_version_id', sa.String(36), sa.ForeignKey('constitutions.id'), nullable=True),
            sa.Column('amendment_date', sa.DateTime(), nullable=True),
            sa.Column('amendment_reason', sa.Text(), nullable=True),
            sa.Column('effective_date', sa.DateTime(), nullable=False),
            sa.Column('archived_date', sa.DateTime(), nullable=True),
            sa.Column('is_active', sa.Boolean(), server_default='true'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
        )
        op.create_index('idx_constitution_version', 'constitutions', ['version'])
        op.create_index('idx_constitution_version_number', 'constitutions', ['version_number'])
        op.create_index('idx_constitution_active', 'constitutions', ['is_active'])
        op.create_index('idx_constitution_effective', 'constitutions', ['effective_date'])

    # =========================================================================
    # 7. TASKS
    # =========================================================================
    if 'tasks' not in existing_tables:
        enum_exists = conn.execute(text(
            "SELECT 1 FROM pg_type WHERE typname = 'taskstatus'"
        )).fetchone()

        if enum_exists:
            op.create_table(
                'tasks',
                sa.Column('id', sa.String(36), primary_key=True),
                sa.Column('agentium_id', sa.String(20), unique=True, nullable=True),
                sa.Column('title', sa.String(200), nullable=False),
                sa.Column('description', sa.Text(), nullable=False),
                sa.Column('status', postgresql.ENUM(
                    'pending', 'deliberating', 'approved', 'rejected', 'delegating',
                    'assigned', 'in_progress', 'review', 'completed', 'failed', 'cancelled',
                    'idle_pending', 'idle_running', 'idle_paused', 'idle_completed',
                    'PENDING', 'DELIBERATING', 'APPROVED', 'REJECTED', 'DELEGATING',
                    'ASSIGNED', 'IN_PROGRESS', 'REVIEW', 'COMPLETED', 'FAILED',
                    'CANCELLED', 'IDLE_PENDING', 'IDLE_RUNNING', 'IDLE_PAUSED',
                    'IDLE_COMPLETED', 'ESCALATED',
                    name='taskstatus', create_type=False),
                    server_default='pending', nullable=False),
                sa.Column('priority', sa.Integer(), server_default='1'),
                sa.Column('assigned_to_agent_id', sa.String(36), sa.ForeignKey('agents.id'), nullable=True),
                sa.Column('created_by', sa.String(36), nullable=False),
                sa.Column('started_at', sa.DateTime(), nullable=True),
                sa.Column('completed_at', sa.DateTime(), nullable=True),
                sa.Column('result_summary', sa.Text(), nullable=True),
                sa.Column('acceptance_criteria', sa.JSON(), nullable=True),
                sa.Column('veto_authority', sa.String(20), nullable=True),
                sa.Column('task_type', sa.String(50), server_default='execution'),
                sa.Column('constitutional_basis', sa.Text(), nullable=True),
                sa.Column('hierarchical_id', sa.String(100), nullable=True),
                sa.Column('recurrence_pattern', sa.String(100), nullable=True),
                sa.Column('parent_task_id', sa.String(36), sa.ForeignKey('tasks.id'), nullable=True),
                sa.Column('execution_plan_id', sa.String(36), nullable=True),
                sa.Column('is_idle_task', sa.Boolean(), server_default='false'),
                sa.Column('idle_task_category', sa.String(50), nullable=True),
                sa.Column('estimated_tokens', sa.Integer(), server_default='0'),
                sa.Column('tokens_used', sa.Integer(), server_default='0'),
                sa.Column('status_history', sa.JSON(), server_default='[]'),
                sa.Column('head_of_council_id', sa.String(36), sa.ForeignKey('agents.id'), nullable=True),
                sa.Column('assigned_council_ids', sa.JSON(), server_default='[]'),
                sa.Column('lead_agent_id', sa.String(36), sa.ForeignKey('agents.id'), nullable=True),
                sa.Column('assigned_task_agent_ids', sa.JSON(), server_default='[]'),
                sa.Column('requires_deliberation', sa.Boolean(), server_default='true'),
                sa.Column('deliberation_id', sa.String(36), nullable=True),
                sa.Column('approved_by_council', sa.Boolean(), server_default='false'),
                sa.Column('approved_by_head', sa.Boolean(), server_default='false'),
                sa.Column('execution_plan', sa.Text(), nullable=True),
                sa.Column('execution_context', sa.Text(), nullable=True),
                sa.Column('tools_allowed', sa.JSON(), server_default='[]'),
                sa.Column('sandbox_mode', sa.Boolean(), server_default='true'),
                sa.Column('result_data', sa.JSON(), nullable=True),
                sa.Column('result_files', sa.JSON(), nullable=True),
                sa.Column('completion_percentage', sa.Integer(), server_default='0'),
                sa.Column('due_date', sa.DateTime(), nullable=True),
                sa.Column('time_estimated', sa.Integer(), server_default='0'),
                sa.Column('time_actual', sa.Integer(), server_default='0'),
                sa.Column('error_count', sa.Integer(), server_default='0'),
                sa.Column('last_error', sa.Text(), nullable=True),
                sa.Column('retry_count', sa.Integer(), server_default='0'),
                sa.Column('max_retries', sa.Integer(), server_default='5'),
                sa.Column('is_active', sa.Boolean(), server_default='true'),
                sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
                sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
                sa.Column('deleted_at', sa.DateTime(), nullable=True),
            )
        else:
            print("WARNING: taskstatus enum does not exist, skipping tasks table creation")

    # =========================================================================
    # 8. SUBTASKS
    # =========================================================================
    if 'subtasks' not in existing_tables:
        op.create_table(
            'subtasks',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('task_id', sa.String(36), sa.ForeignKey('tasks.id')),
            sa.Column('agentium_id', sa.String(20), unique=True, nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('status', sa.String(20), server_default='pending'),
            sa.Column('assigned_to_agent_id', sa.String(36), sa.ForeignKey('agents.id'), nullable=True),
            sa.Column('execution_order', sa.Integer(), server_default='0'),
            sa.Column('result', sa.Text(), nullable=True),
            sa.Column('is_active', sa.Boolean(), server_default='true'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
        )

    # =========================================================================
    # 9. TASK DELIBERATIONS
    # =========================================================================
    if 'task_deliberations' not in existing_tables:
        op.create_table(
            'task_deliberations',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('agentium_id', sa.String(20), unique=True, nullable=False),
            sa.Column('task_id', sa.String(36), sa.ForeignKey('tasks.id'), nullable=False),
            sa.Column('participating_members', sa.JSON(), nullable=False),
            sa.Column('required_approvals', sa.Integer(), server_default='2'),
            sa.Column('min_quorum', sa.Integer(), server_default='2'),
            sa.Column('status', sa.String(20), server_default='pending'),
            sa.Column('started_at', sa.DateTime(), nullable=True),
            sa.Column('ended_at', sa.DateTime(), nullable=True),
            sa.Column('time_limit_minutes', sa.Integer(), server_default='30'),
            sa.Column('votes_for', sa.Integer(), server_default='0'),
            sa.Column('votes_against', sa.Integer(), server_default='0'),
            sa.Column('votes_abstain', sa.Integer(), server_default='0'),
            sa.Column('final_decision', sa.String(20), nullable=True),
            sa.Column('head_overridden', sa.Boolean(), server_default='false'),
            sa.Column('head_override_reason', sa.Text(), nullable=True),
            sa.Column('head_override_at', sa.DateTime(), nullable=True),
            sa.Column('discussion_thread', sa.JSON(), server_default='[]'),
            sa.Column('is_active', sa.Boolean(), server_default='true'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
        )

    # Add FK from tasks to deliberations if both exist
    if 'tasks' in existing_tables and 'task_deliberations' in existing_tables:
        try:
            op.create_foreign_key('tasks_deliberation_id_fkey', 'tasks', 'task_deliberations',
                                  ['deliberation_id'], ['id'])
        except Exception:
            pass

    # =========================================================================
    # 10. TASK EVENTS & AUDIT LOGS
    # =========================================================================
    if 'task_events' not in existing_tables:
        op.create_table(
            'task_events',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('agentium_id', sa.String(20), unique=True, nullable=False),
            sa.Column('task_id', sa.String(36), sa.ForeignKey('tasks.id'), nullable=False),
            sa.Column('event_type', sa.String(50), nullable=False),
            sa.Column('actor_id', sa.String(36), nullable=False),
            sa.Column('actor_type', sa.String(20), server_default='system'),
            sa.Column('data', sa.JSON(), server_default='{}'),
            sa.Column('sequence_number', sa.Integer(), nullable=True),
            sa.Column('is_active', sa.Boolean(), server_default='true'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
        )

    if 'task_audit_logs' not in existing_tables:
        op.create_table(
            'task_audit_logs',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('agentium_id', sa.String(20), nullable=False),
            sa.Column('task_id', sa.String(36), sa.ForeignKey('tasks.id'), nullable=False),
            sa.Column('action', sa.String(50), nullable=False),
            sa.Column('action_details', sa.JSON(), server_default='{}'),
            sa.Column('ip_address', sa.String(45), nullable=True),
            sa.Column('user_agent', sa.String(200), nullable=True),
            sa.Column('is_active', sa.Boolean(), server_default='true'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
        )

    # =========================================================================
    # 11. AMENDMENT VOTING
    # =========================================================================
    if 'amendment_votings' not in existing_tables:
        op.create_table(
            'amendment_votings',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('agentium_id', sa.String(20), unique=True, nullable=False),
            sa.Column('amendment_id', sa.String(36), sa.ForeignKey('constitutions.id')),
            sa.Column('proposed_by_agentium_id', sa.String(10), nullable=False),
            sa.Column('proposed_changes', sa.Text(), nullable=False),
            sa.Column('rationale', sa.Text(), nullable=False),
            sa.Column('status', sa.String(20), server_default='proposed'),
            sa.Column('required_votes', sa.Integer(), server_default='3'),
            sa.Column('eligible_voters', sa.JSON(), server_default='[]'),
            sa.Column('supermajority_threshold', sa.Integer(), server_default='66'),
            sa.Column('votes_for', sa.Integer(), server_default='0'),
            sa.Column('votes_against', sa.Integer(), server_default='0'),
            sa.Column('votes_abstain', sa.Integer(), server_default='0'),
            sa.Column('final_result', sa.String(20), nullable=True),
            sa.Column('started_at', sa.DateTime(), nullable=True),
            sa.Column('ended_at', sa.DateTime(), nullable=True),
            sa.Column('approved_by_agentium_id', sa.String(10), nullable=True),
            sa.Column('approved_at', sa.DateTime(), nullable=True),
            sa.Column('rejection_reason', sa.Text(), nullable=True),
            sa.Column('discussion_thread', sa.JSON(), server_default='[]'),
            sa.Column('is_active', sa.Boolean(), server_default='true'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
        )
        op.create_index('idx_amendment_status', 'amendment_votings', ['status'])
        op.create_index('idx_amendment_constitution', 'amendment_votings', ['amendment_id'])

    # =========================================================================
    # 12. INDIVIDUAL VOTES
    # =========================================================================
    if 'individual_votes' not in existing_tables:
        op.create_table(
            'individual_votes',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('agentium_id', sa.String(20), unique=True, nullable=False),
            sa.Column('amendment_voting_id', sa.String(36), sa.ForeignKey('amendment_votings.id'), nullable=True),
            sa.Column('task_deliberation_id', sa.String(36), sa.ForeignKey('task_deliberations.id'), nullable=True),
            sa.Column('voter_agentium_id', sa.String(10), nullable=False),
            sa.Column('vote', sa.String(10), nullable=False),
            sa.Column('voted_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('rationale', sa.Text(), nullable=True),
            sa.Column('vote_changed', sa.Boolean(), server_default='false'),
            sa.Column('original_vote', sa.String(10), nullable=True),
            sa.Column('changed_at', sa.DateTime(), nullable=True),
            sa.Column('is_active', sa.Boolean(), server_default='true'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
        )
        try:
            op.execute("ALTER TABLE individual_votes ADD CONSTRAINT check_vote_has_parent "
                       "CHECK (task_deliberation_id IS NOT NULL OR amendment_voting_id IS NOT NULL)")
        except Exception:
            pass

    # =========================================================================
    # 13. VOTING RECORDS
    # =========================================================================
    if 'voting_records' not in existing_tables:
        op.create_table(
            'voting_records',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('agentium_id', sa.String(20), unique=True, nullable=False),
            sa.Column('voter_agentium_id', sa.String(10), sa.ForeignKey('agents.agentium_id'), nullable=False),
            sa.Column('period_start', sa.DateTime(), nullable=False),
            sa.Column('period_end', sa.DateTime(), nullable=False),
            sa.Column('total_votes_cast', sa.Integer(), server_default='0'),
            sa.Column('votes_for', sa.Integer(), server_default='0'),
            sa.Column('votes_against', sa.Integer(), server_default='0'),
            sa.Column('votes_abstain', sa.Integer(), server_default='0'),
            sa.Column('votes_changed', sa.Integer(), server_default='0'),
            sa.Column('deliberations_participated', sa.Integer(), server_default='0'),
            sa.Column('deliberations_missed', sa.Integer(), server_default='0'),
            sa.Column('avg_participation_rate', sa.Integer(), server_default='0'),
            sa.Column('proposals_made', sa.Integer(), server_default='0'),
            sa.Column('proposals_accepted', sa.Integer(), server_default='0'),
            sa.Column('is_active', sa.Boolean(), server_default='true'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
        )

    # =========================================================================
    # 14. AUDIT LOGS
    # =========================================================================
    if 'audit_logs' not in existing_tables:
        op.create_table(
            'audit_logs',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('agentium_id', sa.String(20), unique=True, nullable=False),
            sa.Column('level', sa.String(20), nullable=False),
            sa.Column('category', sa.String(30), nullable=False),
            sa.Column('actor_type', sa.String(20), nullable=False),
            sa.Column('actor_id', sa.String(50), nullable=False),
            sa.Column('action', sa.String(100), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('target_type', sa.String(50), nullable=True),
            sa.Column('target_id', sa.String(36), nullable=True),
            sa.Column('session_id', sa.String(100), nullable=True),
            sa.Column('ip_address', sa.String(45), nullable=True),
            sa.Column('before_state', sa.Text(), nullable=True),
            sa.Column('after_state', sa.Text(), nullable=True),
            sa.Column('metadata_json', sa.Text(), nullable=True),
            sa.Column('success', sa.String(1), server_default='Y', nullable=False),
            sa.Column('result_message', sa.Text(), nullable=True),
            sa.Column('error_code', sa.String(50), nullable=True),
            sa.Column('error_details', sa.Text(), nullable=True),
            sa.Column('parent_audit_id', sa.String(36), sa.ForeignKey('audit_logs.id'), nullable=True),
            sa.Column('correlation_id', sa.String(36), nullable=True),
            sa.Column('duration_ms', sa.Integer(), nullable=True),
            sa.Column('memory_delta_mb', sa.Integer(), nullable=True),
            sa.Column('is_active', sa.Boolean(), server_default='true'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
        )
        op.create_index('idx_audit_timestamp', 'audit_logs', ['created_at'])
        op.create_index('idx_audit_actor_action', 'audit_logs', ['actor_id', 'action'])
        op.create_index('idx_audit_level_category', 'audit_logs', ['level', 'category'])
        op.create_index('idx_audit_correlation', 'audit_logs', ['correlation_id'])

    # =========================================================================
    # 15. CHANNELS
    # =========================================================================
    if 'channels' not in existing_tables:
        op.create_table(
            'channels',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('agentium_id', sa.String(20), unique=True, nullable=False),
            sa.Column('name', sa.String(100), nullable=False),
            sa.Column('channel_type', sa.String(20), nullable=False),
            sa.Column('webhook_url', sa.String(500), nullable=True),
            sa.Column('api_key_encrypted', sa.Text(), nullable=True),
            sa.Column('config_json', sa.Text(), nullable=True),
            sa.Column('is_active', sa.Boolean(), server_default='true'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
        )

    # =========================================================================
    # 16. EXTERNAL CHANNELS & MESSAGES
    #     Includes 002_schema WhatsApp provider default + 004 user_id column
    # =========================================================================
    if 'external_channels' not in existing_tables:
        op.create_table(
            'external_channels',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('agentium_id', sa.String(20), unique=True, nullable=False),
            sa.Column('name', sa.String(100), nullable=False),
            sa.Column('channel_type', sa.String(20), nullable=False),
            sa.Column('status', sa.String(20), server_default='pending'),
            sa.Column('config', sa.JSON(), server_default='{}'),
            sa.Column('default_agent_id', sa.String(36), sa.ForeignKey('agents.id'), nullable=True),
            sa.Column('auto_create_tasks', sa.Boolean(), server_default='true'),
            sa.Column('require_approval', sa.Boolean(), server_default='false'),
            sa.Column('webhook_path', sa.String(100), unique=True, nullable=True),
            sa.Column('messages_received', sa.Integer(), server_default='0'),
            sa.Column('messages_sent', sa.Integer(), server_default='0'),
            sa.Column('last_message_at', sa.DateTime(), nullable=True),
            sa.Column('last_tested_at', sa.DateTime(), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            # 004: per-user isolation
            sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('is_active', sa.Boolean(), server_default='true'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
        )

    # 002_schema: seed WhatsApp channels with cloud_api provider default
    op.execute("""
        UPDATE external_channels
        SET config = (
            jsonb_set(
                COALESCE(config::jsonb, '{}'::jsonb),
                '{provider}',
                '"cloud_api"'
            )
        )::json
        WHERE channel_type = 'whatsapp'
          AND (config IS NULL OR config->>'provider' IS NULL)
    """)
    op.execute("""
        COMMENT ON COLUMN external_channels.config IS
        'Channel configuration JSON. For WhatsApp: includes provider (cloud_api|web_bridge), credentials, and connection settings'
    """)

    if 'external_messages' not in existing_tables:
        op.create_table(
            'external_messages',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('agentium_id', sa.String(20), unique=True, nullable=False),
            sa.Column('channel_id', sa.String(36), sa.ForeignKey('external_channels.id'), nullable=False),
            sa.Column('sender_id', sa.String(200), nullable=False),
            sa.Column('sender_name', sa.String(100), nullable=True),
            sa.Column('sender_metadata', sa.JSON(), server_default='{}'),
            sa.Column('message_type', sa.String(20), server_default='text'),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('media_url', sa.String(500), nullable=True),
            sa.Column('raw_payload', sa.JSON(), nullable=True),
            sa.Column('status', sa.String(20), server_default='received'),
            sa.Column('assigned_agent_id', sa.String(36), sa.ForeignKey('agents.id'), nullable=True),
            sa.Column('task_id', sa.String(36), sa.ForeignKey('tasks.id'), nullable=True),
            sa.Column('response_content', sa.Text(), nullable=True),
            sa.Column('responded_at', sa.DateTime(), nullable=True),
            sa.Column('responded_by_agent_id', sa.String(36), sa.ForeignKey('agents.id'), nullable=True),
            sa.Column('error_count', sa.Integer(), server_default='0'),
            sa.Column('last_error', sa.Text(), nullable=True),
            sa.Column('is_active', sa.Boolean(), server_default='true'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
        )

    # =========================================================================
    # 17. SYSTEM SETTINGS
    # =========================================================================
    if 'system_settings' not in existing_tables:
        op.create_table(
            'system_settings',
            sa.Column('key', sa.String(128), primary_key=True),
            sa.Column('value', sa.Text(), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        )
        op.execute("""
            INSERT INTO system_settings (key, value, description, updated_at) VALUES
                ('daily_token_limit', '100000', 'Maximum tokens per day across all API providers', NOW()),
                ('daily_cost_limit', '5.0', 'Maximum USD cost per day across all API providers', NOW())
            ON CONFLICT (key) DO NOTHING
        """)

    # =========================================================================
    # 18. MODEL USAGE LOGS
    # =========================================================================
    if 'model_usage_logs' not in existing_tables:
        op.create_table(
            'model_usage_logs',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('agentium_id', sa.String(10), unique=True, nullable=False),
            sa.Column('config_id', sa.String(36), sa.ForeignKey('user_model_configs.id'), nullable=False),
            sa.Column('provider', sa.String(30), nullable=False),
            sa.Column('model_used', sa.String(100), nullable=False),
            sa.Column('request_type', sa.String(50), server_default='chat'),
            sa.Column('total_tokens', sa.Integer(), server_default='0'),
            sa.Column('prompt_tokens', sa.Integer(), nullable=True),
            sa.Column('completion_tokens', sa.Integer(), nullable=True),
            sa.Column('latency_ms', sa.Integer(), nullable=True),
            sa.Column('success', sa.Boolean(), server_default='true'),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('cost_usd', sa.Float(), nullable=True),
            sa.Column('request_metadata', sa.JSON(), nullable=True),
            sa.Column('is_active', sa.Boolean(), server_default='true'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
        )
        op.create_index('idx_usage_config', 'model_usage_logs', ['config_id'])
        op.create_index('idx_usage_created', 'model_usage_logs', ['created_at'])
        op.create_index('idx_usage_provider', 'model_usage_logs', ['provider'])

    # =========================================================================
    # 19. CONVERSATIONS & CHAT MESSAGES
    #     Includes 004 unified-inbox alignment columns
    # =========================================================================
    if 'conversations' not in existing_tables:
        op.create_table(
            'conversations',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('title', sa.String(200), nullable=True),
            sa.Column('context', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('last_message_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('is_deleted', sa.Boolean(), server_default='false'),
            sa.Column('is_archived', sa.Boolean(), server_default='false'),
            # 004: active-state flag
            sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
        )
        op.create_index('idx_conv_user_updated', 'conversations', ['user_id', 'updated_at'])
        op.create_index('idx_conv_last_message', 'conversations', ['last_message_at'])

    if 'chat_messages' not in existing_tables:
        op.create_table(
            'chat_messages',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('conversation_id', sa.String(36), sa.ForeignKey('conversations.id'), nullable=True),
            sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('role', sa.String(50), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('attachments', sa.JSON(), nullable=True),
            sa.Column('message_metadata', sa.JSON(), nullable=True),
            sa.Column('agent_id', sa.String(50), nullable=True),
            # 004: unified-inbox fields
            sa.Column('sender_channel', sa.String(50), nullable=True),
            sa.Column('message_type', sa.String(50), server_default='text', nullable=True),
            sa.Column('media_url', sa.Text(), nullable=True),
            sa.Column('silent_delivery', sa.Boolean(), server_default='false', nullable=True),
            sa.Column('external_message_id', sa.String(100), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('is_deleted', sa.Boolean(), server_default='false'),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
        )
        op.create_index('idx_chat_user_created', 'chat_messages', ['user_id', 'created_at'])
        op.create_index('idx_chat_conversation', 'chat_messages', ['conversation_id', 'created_at'])
        op.create_index('idx_chat_role', 'chat_messages', ['role'])

    # =========================================================================
    # 20. MONITORING TABLES
    # =========================================================================
    if 'agent_health_reports' not in existing_tables:
        op.create_table(
            'agent_health_reports',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('agentium_id', sa.String(10), unique=True, nullable=False),
            sa.Column('monitor_agent_id', sa.String(36), sa.ForeignKey('agents.id'), nullable=False),
            sa.Column('monitor_agentium_id', sa.String(10), nullable=False),
            sa.Column('subject_agent_id', sa.String(36), sa.ForeignKey('agents.id'), nullable=False),
            sa.Column('subject_agentium_id', sa.String(10), nullable=False),
            sa.Column('status', sa.String(30), server_default='healthy'),
            sa.Column('overall_health_score', sa.Float(), server_default='100.0'),
            sa.Column('task_success_rate', sa.Float(), nullable=True),
            sa.Column('avg_task_duration', sa.Integer(), nullable=True),
            sa.Column('constitution_violations_count', sa.Integer(), server_default='0'),
            sa.Column('last_response_time_ms', sa.Integer(), nullable=True),
            sa.Column('findings', sa.JSON(), nullable=True),
            sa.Column('recommendations', sa.Text(), nullable=True),
            sa.Column('reviewed_by_higher', sa.Boolean(), server_default='false'),
            sa.Column('higher_authority_notes', sa.Text(), nullable=True),
            sa.Column('is_active', sa.Boolean(), server_default='true'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
        )
        op.create_index('idx_health_monitor', 'agent_health_reports', ['monitor_agent_id'])
        op.create_index('idx_health_subject', 'agent_health_reports', ['subject_agent_id'])

    if 'violation_reports' not in existing_tables:
        op.create_table(
            'violation_reports',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('agentium_id', sa.String(10), unique=True, nullable=False),
            sa.Column('reporter_agent_id', sa.String(36), sa.ForeignKey('agents.id'), nullable=False),
            sa.Column('reporter_agentium_id', sa.String(10), nullable=False),
            sa.Column('violator_agent_id', sa.String(36), sa.ForeignKey('agents.id'), nullable=False),
            sa.Column('violator_agentium_id', sa.String(10), nullable=False),
            sa.Column('severity', sa.String(20), nullable=False),
            sa.Column('violated_article', sa.String(50), nullable=True),
            sa.Column('violated_ethos_rule', sa.String(200), nullable=True),
            sa.Column('violation_type', sa.String(50), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('evidence', sa.JSON(), nullable=True),
            sa.Column('context', sa.JSON(), nullable=True),
            sa.Column('status', sa.String(20), server_default='open'),
            sa.Column('assigned_to', sa.String(10), nullable=True),
            sa.Column('resolution', sa.Text(), nullable=True),
            sa.Column('action_taken', sa.String(50), nullable=True),
            sa.Column('violator_terminated', sa.Boolean(), server_default='false'),
            sa.Column('is_active', sa.Boolean(), server_default='true'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
        )

    if 'task_verifications' not in existing_tables:
        op.create_table(
            'task_verifications',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('agentium_id', sa.String(10), unique=True, nullable=False),
            sa.Column('task_id', sa.String(36), sa.ForeignKey('tasks.id'), nullable=False),
            sa.Column('subtask_id', sa.String(36), sa.ForeignKey('subtasks.id'), nullable=True),
            sa.Column('task_agent_id', sa.String(36), sa.ForeignKey('agents.id'), nullable=False),
            sa.Column('lead_agent_id', sa.String(36), sa.ForeignKey('agents.id'), nullable=False),
            sa.Column('submitted_output', sa.Text(), nullable=False),
            sa.Column('submitted_data', sa.JSON(), nullable=True),
            sa.Column('submitted_at', sa.DateTime(), nullable=False),
            sa.Column('checks_performed', sa.JSON(), nullable=True),
            sa.Column('constitution_compliant', sa.Boolean(), nullable=True),
            sa.Column('output_accurate', sa.Boolean(), nullable=True),
            sa.Column('meets_requirements', sa.Boolean(), nullable=True),
            sa.Column('verification_status', sa.String(20), server_default='pending'),
            sa.Column('rejection_reason', sa.Text(), nullable=True),
            sa.Column('revision_count', sa.Integer(), server_default='0'),
            sa.Column('corrections_made', sa.Text(), nullable=True),
            sa.Column('feedback_to_agent', sa.Text(), nullable=True),
            sa.Column('escalated_to_council', sa.Boolean(), server_default='false'),
            sa.Column('escalation_reason', sa.Text(), nullable=True),
            sa.Column('is_active', sa.Boolean(), server_default='true'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
        )

    if 'performance_metrics' not in existing_tables:
        op.create_table(
            'performance_metrics',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('agentium_id', sa.String(10), unique=True, nullable=False),
            sa.Column('agent_id', sa.String(36), sa.ForeignKey('agents.id'), nullable=False),
            sa.Column('calculated_by_agent_id', sa.String(36), sa.ForeignKey('agents.id'), nullable=False),
            sa.Column('period_start', sa.DateTime(), nullable=False),
            sa.Column('period_end', sa.DateTime(), nullable=False),
            sa.Column('tasks_assigned', sa.Integer(), server_default='0'),
            sa.Column('tasks_completed', sa.Integer(), server_default='0'),
            sa.Column('tasks_failed', sa.Integer(), server_default='0'),
            sa.Column('tasks_rejected', sa.Integer(), server_default='0'),
            sa.Column('avg_quality_score', sa.Float(), nullable=True),
            sa.Column('constitution_violations', sa.Integer(), server_default='0'),
            sa.Column('avg_response_time', sa.Float(), nullable=True),
            sa.Column('total_tokens_used', sa.Integer(), server_default='0'),
            sa.Column('trend', sa.String(20), nullable=True),
            sa.Column('recommended_action', sa.String(50), nullable=True),
            sa.Column('is_active', sa.Boolean(), server_default='true'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
        )

    if 'monitoring_alerts' not in existing_tables:
        op.create_table(
            'monitoring_alerts',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('agentium_id', sa.String(10), unique=True, nullable=False),
            sa.Column('alert_type', sa.String(50), nullable=False),
            sa.Column('severity', sa.String(20), nullable=False),
            sa.Column('detected_by_agent_id', sa.String(36), sa.ForeignKey('agents.id'), nullable=False),
            sa.Column('affected_agent_id', sa.String(36), sa.ForeignKey('agents.id'), nullable=True),
            sa.Column('message', sa.Text(), nullable=False),
            sa.Column('alert_metadata', sa.JSON(), nullable=True),
            sa.Column('notified_agents', sa.JSON(), nullable=True),
            sa.Column('acknowledged_by', sa.String(10), nullable=True),
            sa.Column('resolved_by', sa.String(10), nullable=True),
            sa.Column('status', sa.String(20), server_default='active'),
            sa.Column('is_active', sa.Boolean(), server_default='true'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
        )

    # =========================================================================
    # 21. CRITIQUE REVIEWS
    # =========================================================================
    if 'critique_reviews' not in existing_tables:
        op.create_table(
            'critique_reviews',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('agentium_id', sa.String(10), unique=True, nullable=False),
            sa.Column('task_id', sa.String(36), sa.ForeignKey('tasks.id'), nullable=False),
            sa.Column('subtask_id', sa.String(36), sa.ForeignKey('subtasks.id'), nullable=True),
            sa.Column('critic_type', sa.String(20), nullable=False),
            sa.Column('critic_agentium_id', sa.String(10), nullable=False),
            sa.Column('verdict', sa.String(20), nullable=False),
            sa.Column('rejection_reason', sa.Text(), nullable=True),
            sa.Column('suggestions', sa.Text(), nullable=True),
            sa.Column('retry_count', sa.Integer(), server_default='0'),
            sa.Column('max_retries', sa.Integer(), server_default='5'),
            sa.Column('review_duration_ms', sa.Float(), server_default='0.0'),
            sa.Column('model_used', sa.String(100), nullable=True),
            sa.Column('output_hash', sa.String(64), nullable=True),
            sa.Column('reviewed_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('criteria_results', sa.JSON(), nullable=True),
            sa.Column('criteria_evaluated', sa.Integer(), nullable=True),
            sa.Column('criteria_passed', sa.Integer(), nullable=True),
            sa.Column('is_active', sa.Boolean(), server_default='true'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
        )
        op.create_index('idx_critique_task', 'critique_reviews', ['task_id'])
        op.create_index('idx_critique_critic', 'critique_reviews', ['critic_agentium_id'])

    # =========================================================================
    # 22. TOOL MANAGEMENT
    # =========================================================================
    if 'tool_staging' not in existing_tables:
        op.create_table(
            'tool_staging',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('tool_name', sa.String(100), nullable=False, unique=True),
            sa.Column('proposed_by_agentium_id', sa.String(10), nullable=False),
            sa.Column('tool_path', sa.String(500), nullable=False),
            sa.Column('request_json', sa.Text(), nullable=False),
            sa.Column('requires_vote', sa.Boolean(), server_default='true'),
            sa.Column('voting_id', sa.String(36), nullable=True),
            sa.Column('status', sa.String(50), server_default='pending_approval'),
            sa.Column('current_version', sa.Integer(), server_default='1'),
            sa.Column('activated_at', sa.DateTime(), nullable=True),
            sa.Column('deprecated_at', sa.DateTime(), nullable=True),
            sa.Column('sunset_at', sa.DateTime(), nullable=True),
            sa.Column('deprecated_by_agentium_id', sa.String(10), nullable=True),
            sa.Column('deprecation_reason', sa.Text(), nullable=True),
            sa.Column('replacement_tool_name', sa.String(100), nullable=True),
            sa.Column('is_active', sa.Boolean(), server_default='true'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
        )
        op.create_index('idx_tool_staging_name', 'tool_staging', ['tool_name'])
        op.create_index('idx_tool_staging_proposer', 'tool_staging', ['proposed_by_agentium_id'])
        op.create_index('idx_tool_staging_status', 'tool_staging', ['status'])

    if 'tool_versions' not in existing_tables:
        op.create_table(
            'tool_versions',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('tool_name', sa.String(100), nullable=False),
            sa.Column('version_number', sa.Integer(), nullable=False),
            sa.Column('version_tag', sa.String(20), nullable=False),
            sa.Column('code_snapshot', sa.Text(), nullable=False),
            sa.Column('tool_path', sa.String(500), nullable=False),
            sa.Column('authored_by_agentium_id', sa.String(10), nullable=False),
            sa.Column('change_summary', sa.Text(), nullable=True),
            sa.Column('approved_by_voting_id', sa.String(36), nullable=True),
            sa.Column('approved_at', sa.DateTime(), nullable=True),
            sa.Column('is_active', sa.Boolean(), server_default='false'),
            sa.Column('is_rolled_back', sa.Boolean(), server_default='false'),
            sa.Column('rolled_back_from_version', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
        )
        op.create_index('ix_tool_versions_name_number', 'tool_versions',
                        ['tool_name', 'version_number'], unique=True)

    if 'tool_usage_logs' not in existing_tables:
        op.create_table(
            'tool_usage_logs',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('tool_name', sa.String(100), nullable=False),
            sa.Column('tool_version', sa.Integer(), server_default='1'),
            sa.Column('called_by_agentium_id', sa.String(10), nullable=False),
            sa.Column('task_id', sa.String(36), nullable=True),
            sa.Column('success', sa.Boolean(), nullable=False),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('latency_ms', sa.Float(), nullable=True),
            sa.Column('input_hash', sa.String(64), nullable=True),
            sa.Column('output_size_bytes', sa.Integer(), nullable=True),
            sa.Column('invoked_at', sa.DateTime(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
        )
        op.create_index('ix_tool_usage_tool_invoked', 'tool_usage_logs', ['tool_name', 'invoked_at'])
        op.create_index('ix_tool_usage_agent_tool', 'tool_usage_logs', ['called_by_agentium_id', 'tool_name'])

    if 'tool_marketplace_listings' not in existing_tables:
        op.create_table(
            'tool_marketplace_listings',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('tool_name', sa.String(100), nullable=False),
            sa.Column('version_tag', sa.String(20), nullable=False),
            sa.Column('publisher_instance_id', sa.String(100), nullable=False),
            sa.Column('published_by_agentium_id', sa.String(10), nullable=True),
            sa.Column('display_name', sa.String(200), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('category', sa.String(50), nullable=True),
            sa.Column('tags', sa.JSON(), server_default='[]'),
            sa.Column('code_snapshot', sa.Text(), nullable=False),
            sa.Column('code_hash', sa.String(64), nullable=False),
            sa.Column('parameters_schema', sa.JSON(), server_default='{}'),
            sa.Column('authorized_tiers', sa.JSON(), server_default='[]'),
            sa.Column('is_local', sa.Boolean(), server_default='true'),
            sa.Column('is_imported', sa.Boolean(), server_default='false'),
            sa.Column('import_source_url', sa.String(500), nullable=True),
            sa.Column('is_verified', sa.Boolean(), server_default='false'),
            sa.Column('trust_score', sa.Float(), server_default='0.0'),
            sa.Column('download_count', sa.Integer(), server_default='0'),
            sa.Column('rating_sum', sa.Float(), server_default='0.0'),
            sa.Column('rating_count', sa.Integer(), server_default='0'),
            sa.Column('is_active', sa.Boolean(), server_default='true'),
            sa.Column('published_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('yanked_at', sa.DateTime(), nullable=True),
            sa.Column('yank_reason', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
        )

    # =========================================================================
    # 23. SCHEDULED TASKS
    # =========================================================================
    if 'scheduled_tasks' not in existing_tables:
        op.create_table(
            'scheduled_tasks',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('agentium_id', sa.String(20), unique=True, nullable=False),
            sa.Column('name', sa.String(200), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('cron_expression', sa.String(100), nullable=False),
            sa.Column('task_payload', sa.Text(), nullable=False),
            sa.Column('owner_agentium_id', sa.String(10), nullable=False, server_default='00001'),
            sa.Column('executing_agent_id', sa.String(36), sa.ForeignKey('agents.id'), nullable=True),
            sa.Column('status', sa.String(20), server_default='active'),
            sa.Column('priority', sa.Integer(), server_default='1'),
            sa.Column('last_execution_at', sa.DateTime(), nullable=True),
            sa.Column('next_execution_at', sa.DateTime(), nullable=True),
            sa.Column('execution_count', sa.Integer(), server_default='0'),
            sa.Column('failure_count', sa.Integer(), server_default='0'),
            sa.Column('max_retries', sa.Integer(), server_default='3'),
            sa.Column('timezone', sa.String(50), server_default='UTC'),
            sa.Column('is_active', sa.Boolean(), server_default='true'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
        )
        op.create_index('idx_scheduled_next_run', 'scheduled_tasks', ['next_execution_at'])
        op.create_index('idx_scheduled_owner', 'scheduled_tasks', ['owner_agentium_id'])
        op.create_index('idx_scheduled_status', 'scheduled_tasks', ['status'])

    if 'scheduled_task_executions' not in existing_tables:
        op.create_table(
            'scheduled_task_executions',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('scheduled_task_id', sa.String(36), sa.ForeignKey('scheduled_tasks.id')),
            sa.Column('execution_agentium_id', sa.String(10), nullable=False),
            sa.Column('execution_agent_id', sa.String(36), sa.ForeignKey('agents.id'), nullable=True),
            sa.Column('started_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.Column('status', sa.String(20), server_default='running'),
            sa.Column('result_payload', sa.Text(), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('retry_number', sa.Integer(), server_default='0'),
            sa.Column('is_active', sa.Boolean(), server_default='true'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
        )
        op.create_index('idx_sched_exec_task', 'scheduled_task_executions', ['scheduled_task_id'])
        op.create_index('idx_sched_exec_time', 'scheduled_task_executions', ['started_at'])

    # =========================================================================
    # 24. EXECUTION CHECKPOINTS
    # =========================================================================
    if 'execution_checkpoints' not in existing_tables:
        op.create_table(
            'execution_checkpoints',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('agentium_id', sa.String(20), unique=True, nullable=False),
            sa.Column('session_id', sa.String(100), nullable=False),
            sa.Column('task_id', sa.String(36), sa.ForeignKey('tasks.id'), nullable=False),
            sa.Column('phase', sa.String(50), nullable=False),
            sa.Column('agent_states', sa.JSON(), server_default='{}'),
            sa.Column('artifacts', sa.JSON(), server_default='[]'),
            sa.Column('task_state_snapshot', sa.JSON(), server_default='{}'),
            sa.Column('parent_checkpoint_id', sa.String(36), sa.ForeignKey('execution_checkpoints.id'), nullable=True),
            sa.Column('branch_name', sa.String(100), nullable=True),
            sa.Column('is_active', sa.Boolean(), server_default='true'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
        )
        op.create_index('idx_exec_ckpt_session', 'execution_checkpoints', ['session_id'])
        op.create_index('idx_exec_ckpt_task', 'execution_checkpoints', ['task_id'])

    # =========================================================================
    # 25. REMOTE EXECUTIONS & SANDBOXES  (from 003_add_remote_execution)
    # =========================================================================
    if 'remote_executions' not in existing_tables:
        op.create_table(
            'remote_executions',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('agentium_id', sa.String(length=10), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('execution_id', sa.String(length=50), nullable=False),
            sa.Column('agent_id', sa.String(length=20), nullable=False),
            sa.Column('task_id', sa.String(length=36), nullable=True),
            sa.Column('code', sa.Text(), nullable=False),
            sa.Column('language', sa.String(length=20), nullable=True),
            sa.Column('dependencies', postgresql.JSON(astext_type=sa.Text()), nullable=True),
            sa.Column('input_data_schema', postgresql.JSON(astext_type=sa.Text()), nullable=True),
            sa.Column('expected_output_schema', postgresql.JSON(astext_type=sa.Text()), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=True),
            sa.Column('summary', postgresql.JSON(astext_type=sa.Text()), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('cpu_time_seconds', sa.Float(), nullable=True),
            sa.Column('memory_peak_mb', sa.Float(), nullable=True),
            sa.Column('execution_time_ms', sa.Integer(), nullable=True),
            sa.Column('sandbox_id', sa.String(length=50), nullable=True),
            sa.Column('sandbox_container_id', sa.String(length=100), nullable=True),
            sa.Column('started_at', sa.DateTime(), nullable=True),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['agent_id'], ['agents.agentium_id']),
            sa.ForeignKeyConstraint(['task_id'], ['tasks.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('execution_id'),
        )
        op.create_index('ix_remote_executions_execution_id', 'remote_executions', ['execution_id'])
        op.create_index('ix_remote_executions_agent_id', 'remote_executions', ['agent_id'])
        op.create_index('ix_remote_executions_status', 'remote_executions', ['status'])
        op.create_index('ix_remote_executions_created_at', 'remote_executions', ['created_at'])

    if 'sandboxes' not in existing_tables:
        op.create_table(
            'sandboxes',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('agentium_id', sa.String(length=10), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('sandbox_id', sa.String(length=50), nullable=False),
            sa.Column('container_id', sa.String(length=100), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=True),
            sa.Column('cpu_limit', sa.Float(), nullable=True),
            sa.Column('memory_limit_mb', sa.Integer(), nullable=True),
            sa.Column('timeout_seconds', sa.Integer(), nullable=True),
            sa.Column('network_mode', sa.String(length=20), nullable=True),
            sa.Column('allowed_hosts', postgresql.JSON(astext_type=sa.Text()), nullable=True),
            sa.Column('volume_mounts', postgresql.JSON(astext_type=sa.Text()), nullable=True),
            sa.Column('max_disk_mb', sa.Integer(), nullable=True),
            sa.Column('current_execution_id', sa.String(length=50), nullable=True),
            sa.Column('created_by_agent_id', sa.String(length=5), nullable=False),
            sa.Column('last_used_at', sa.DateTime(), nullable=True),
            sa.Column('destroyed_at', sa.DateTime(), nullable=True),
            sa.Column('destroy_reason', sa.String(length=100), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('sandbox_id'),
        )
        op.create_index('ix_sandboxes_sandbox_id', 'sandboxes', ['sandbox_id'])
        op.create_index('ix_sandboxes_agent_id', 'sandboxes', ['created_by_agent_id'])
        op.create_index('ix_sandboxes_status', 'sandboxes', ['status'])

    print("✅ Complete schema migration (001–004 consolidated) finished successfully")


def downgrade():
    tables_to_drop = [
        'sandboxes', 'remote_executions',
        'execution_checkpoints', 'scheduled_task_executions', 'scheduled_tasks',
        'tool_marketplace_listings', 'tool_usage_logs', 'tool_versions', 'tool_staging',
        'critique_reviews', 'monitoring_alerts', 'performance_metrics',
        'task_verifications', 'violation_reports', 'agent_health_reports',
        'chat_messages', 'conversations', 'model_usage_logs',
        'external_messages', 'external_channels',
        'channels', 'audit_logs', 'individual_votes', 'voting_records',
        'amendment_votings', 'task_audit_logs', 'task_events', 'task_deliberations',
        'subtasks', 'tasks', 'constitutions',
        'critic_agents', 'task_agents', 'lead_agents', 'council_members', 'head_of_council',
        'agents', 'ethos', 'user_model_configs', 'users', 'system_settings',
    ]
    for table in tables_to_drop:
        try:
            op.drop_table(table)
        except Exception as e:
            print(f"Note: could not drop {table}: {e}")
    try:
        op.execute("DROP TYPE IF EXISTS taskstatus")
    except Exception as e:
        print(f"Note: could not drop taskstatus enum: {e}")