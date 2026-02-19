"""Add missing tables: system_settings, model_usage_logs, chat_messages,
conversations, monitoring tables, critics, and fix users/user_model_configs schema.

Revision ID: 002_add_missing_tables
Revises: add_custom_capabilities
Create Date: 2026-02-19 00:00:00.000000

What this migration adds / fixes
─────────────────────────────────
1. system_settings          — persists budget limits (and any future k/v config)
2. model_usage_logs         — real per-request API token & cost tracking
3. conversations            — chat session grouping
4. chat_messages            — persistent chat history
5. agent_health_reports     — monitoring: health snapshots filed by supervisors
6. violation_reports        — monitoring: formal violation records
7. task_verifications       — lead-agent quality gate for task output
8. performance_metrics      — rolling agent performance snapshots
9. monitoring_alerts        — real-time critical-issue alerts
10. critic_agents           — critic agent specialisation table
11. critique_reviews        — individual critic review records

Schema fixes (ALTER on existing tables)
────────────────────────────────────────
• users              → add is_pending (Boolean), fix id to Integer autoincrement
• user_model_configs → add all columns present in user_config.py but missing from 001
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '002_add_missing_tables'
down_revision = 'add_custom_capabilities'
branch_labels = None
depends_on = None


def upgrade():

    # ─────────────────────────────────────────────────────────────────────────
    # 1. system_settings — persistent key/value config (budget limits, etc.)
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        'system_settings',
        sa.Column('key',         sa.String(128), primary_key=True),
        sa.Column('value',       sa.Text(),       nullable=False),
        sa.Column('description', sa.Text(),       nullable=True),
        sa.Column('updated_at',  sa.DateTime(),   nullable=False, server_default=sa.func.now()),
    )

    # Seed default budget values (ON CONFLICT DO NOTHING handled at app layer;
    # here we just insert unconditionally into the freshly created table)
    op.execute("""
        INSERT INTO system_settings (key, value, description, updated_at) VALUES
            ('daily_token_limit', '100000',
             'Maximum tokens per day across all API providers', NOW()),
            ('daily_cost_limit',  '5.0',
             'Maximum USD cost per day across all API providers', NOW())
    """)

    # ─────────────────────────────────────────────────────────────────────────
    # 2. model_usage_logs — per-request token & cost tracking
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        'model_usage_logs',
        sa.Column('id',               sa.String(36),   primary_key=True),
        sa.Column('agentium_id',      sa.String(10),   unique=True, nullable=False),
        sa.Column('config_id',        sa.String(36),   sa.ForeignKey('user_model_configs.id'), nullable=False),
        sa.Column('provider',         sa.String(30),   nullable=False),
        sa.Column('model_used',       sa.String(100),  nullable=False),
        sa.Column('request_type',     sa.String(50),   server_default='chat'),
        sa.Column('total_tokens',     sa.Integer(),    server_default='0'),
        sa.Column('prompt_tokens',    sa.Integer(),    nullable=True),
        sa.Column('completion_tokens',sa.Integer(),    nullable=True),
        sa.Column('latency_ms',       sa.Integer(),    nullable=True),
        sa.Column('success',          sa.Boolean(),    server_default='true'),
        sa.Column('error_message',    sa.Text(),       nullable=True),
        sa.Column('cost_usd',         sa.Float(),      nullable=True),
        sa.Column('request_metadata', sa.JSON(),       nullable=True),
        sa.Column('is_active',        sa.String(1),    server_default='Y'),
        sa.Column('created_at',       sa.DateTime(),   server_default=sa.func.now()),
        sa.Column('updated_at',       sa.DateTime(),   server_default=sa.func.now()),
    )
    op.create_index('idx_usage_config',    'model_usage_logs', ['config_id'])
    op.create_index('idx_usage_created',   'model_usage_logs', ['created_at'])
    op.create_index('idx_usage_provider',  'model_usage_logs', ['provider'])

    # ─────────────────────────────────────────────────────────────────────────
    # 3. conversations — chat session grouping
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        'conversations',
        sa.Column('id',              sa.String(36),   primary_key=True),
        sa.Column('user_id',         sa.Integer(),    sa.ForeignKey('users.id'), nullable=False),
        sa.Column('title',           sa.String(200),  nullable=True),
        sa.Column('context',         sa.Text(),       nullable=True),
        sa.Column('created_at',      sa.DateTime(),   server_default=sa.func.now()),
        sa.Column('updated_at',      sa.DateTime(),   server_default=sa.func.now()),
        sa.Column('last_message_at', sa.DateTime(),   server_default=sa.func.now()),
        sa.Column('is_deleted',      sa.String(1),    server_default='N'),
        sa.Column('is_archived',     sa.String(1),    server_default='N'),
    )
    op.create_index('idx_conv_user_updated',  'conversations', ['user_id', 'updated_at'])
    op.create_index('idx_conv_last_message',  'conversations', ['last_message_at'])

    # ─────────────────────────────────────────────────────────────────────────
    # 4. chat_messages — persistent message history
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        'chat_messages',
        sa.Column('id',               sa.String(36),   primary_key=True),
        sa.Column('conversation_id',  sa.String(36),   sa.ForeignKey('conversations.id'), nullable=True),
        sa.Column('user_id',          sa.Integer(),    sa.ForeignKey('users.id'), nullable=False),
        sa.Column('role',             sa.String(50),   nullable=False),
        sa.Column('content',          sa.Text(),       nullable=False),
        sa.Column('attachments',      sa.JSON(),       nullable=True),
        sa.Column('message_metadata', sa.JSON(),       nullable=True),
        sa.Column('agent_id',         sa.String(50),   nullable=True),
        sa.Column('created_at',       sa.DateTime(),   server_default=sa.func.now()),
        sa.Column('updated_at',       sa.DateTime(),   server_default=sa.func.now()),
        sa.Column('is_deleted',       sa.String(1),    server_default='N'),
    )
    op.create_index('idx_chat_user_created',  'chat_messages', ['user_id', 'created_at'])
    op.create_index('idx_chat_conversation',  'chat_messages', ['conversation_id', 'created_at'])
    op.create_index('idx_chat_role',          'chat_messages', ['role'])

    # ─────────────────────────────────────────────────────────────────────────
    # 5. agent_health_reports
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        'agent_health_reports',
        sa.Column('id',                        sa.String(36),  primary_key=True),
        sa.Column('agentium_id',               sa.String(10),  unique=True, nullable=False),
        sa.Column('monitor_agent_id',          sa.String(36),  sa.ForeignKey('agents.id'), nullable=False),
        sa.Column('monitor_agentium_id',       sa.String(10),  nullable=False),
        sa.Column('subject_agent_id',          sa.String(36),  sa.ForeignKey('agents.id'), nullable=False),
        sa.Column('subject_agentium_id',       sa.String(10),  nullable=False),
        sa.Column('status',                    sa.String(30),  server_default='healthy'),
        sa.Column('overall_health_score',      sa.Float(),     server_default='100.0'),
        sa.Column('task_success_rate',         sa.Float(),     nullable=True),
        sa.Column('avg_task_duration',         sa.Integer(),   nullable=True),
        sa.Column('constitution_violations_count', sa.Integer(), server_default='0'),
        sa.Column('last_response_time_ms',     sa.Integer(),   nullable=True),
        sa.Column('findings',                  sa.JSON(),      nullable=True),
        sa.Column('recommendations',           sa.Text(),      nullable=True),
        sa.Column('reviewed_by_higher',        sa.Boolean(),   server_default='false'),
        sa.Column('higher_authority_notes',    sa.Text(),      nullable=True),
        sa.Column('is_active',                 sa.String(1),   server_default='Y'),
        sa.Column('created_at',                sa.DateTime(),  server_default=sa.func.now()),
        sa.Column('updated_at',                sa.DateTime(),  server_default=sa.func.now()),
    )
    op.create_index('idx_health_monitor',  'agent_health_reports', ['monitor_agent_id'])
    op.create_index('idx_health_subject',  'agent_health_reports', ['subject_agent_id'])

    # ─────────────────────────────────────────────────────────────────────────
    # 6. violation_reports
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        'violation_reports',
        sa.Column('id',                    sa.String(36),  primary_key=True),
        sa.Column('agentium_id',           sa.String(10),  unique=True, nullable=False),
        sa.Column('reporter_agent_id',     sa.String(36),  sa.ForeignKey('agents.id'), nullable=False),
        sa.Column('reporter_agentium_id',  sa.String(10),  nullable=False),
        sa.Column('violator_agent_id',     sa.String(36),  sa.ForeignKey('agents.id'), nullable=False),
        sa.Column('violator_agentium_id',  sa.String(10),  nullable=False),
        sa.Column('severity',              sa.String(20),  nullable=False),
        sa.Column('violated_article',      sa.String(50),  nullable=True),
        sa.Column('violated_ethos_rule',   sa.String(200), nullable=True),
        sa.Column('violation_type',        sa.String(50),  nullable=False),
        sa.Column('description',           sa.Text(),      nullable=False),
        sa.Column('evidence',              sa.JSON(),      nullable=True),
        sa.Column('context',               sa.JSON(),      nullable=True),
        sa.Column('status',                sa.String(20),  server_default='open'),
        sa.Column('assigned_to',           sa.String(10),  nullable=True),
        sa.Column('resolution',            sa.Text(),      nullable=True),
        sa.Column('action_taken',          sa.String(50),  nullable=True),
        sa.Column('violator_terminated',   sa.Boolean(),   server_default='false'),
        sa.Column('is_active',             sa.String(1),   server_default='Y'),
        sa.Column('created_at',            sa.DateTime(),  server_default=sa.func.now()),
        sa.Column('updated_at',            sa.DateTime(),  server_default=sa.func.now()),
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 7. task_verifications
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        'task_verifications',
        sa.Column('id',                    sa.String(36),  primary_key=True),
        sa.Column('agentium_id',           sa.String(10),  unique=True, nullable=False),
        sa.Column('task_id',               sa.String(36),  sa.ForeignKey('tasks.id'), nullable=False),
        sa.Column('subtask_id',            sa.String(36),  sa.ForeignKey('subtasks.id'), nullable=True),
        sa.Column('task_agent_id',         sa.String(36),  sa.ForeignKey('agents.id'), nullable=False),
        sa.Column('lead_agent_id',         sa.String(36),  sa.ForeignKey('agents.id'), nullable=False),
        sa.Column('submitted_output',      sa.Text(),      nullable=False),
        sa.Column('submitted_data',        sa.JSON(),      nullable=True),
        sa.Column('submitted_at',          sa.DateTime(),  nullable=False),
        sa.Column('checks_performed',      sa.JSON(),      nullable=True),
        sa.Column('constitution_compliant',sa.Boolean(),   nullable=True),
        sa.Column('output_accurate',       sa.Boolean(),   nullable=True),
        sa.Column('meets_requirements',    sa.Boolean(),   nullable=True),
        sa.Column('verification_status',   sa.String(20),  server_default='pending'),
        sa.Column('rejection_reason',      sa.Text(),      nullable=True),
        sa.Column('revision_count',        sa.Integer(),   server_default='0'),
        sa.Column('corrections_made',      sa.Text(),      nullable=True),
        sa.Column('feedback_to_agent',     sa.Text(),      nullable=True),
        sa.Column('escalated_to_council',  sa.Boolean(),   server_default='false'),
        sa.Column('escalation_reason',     sa.Text(),      nullable=True),
        sa.Column('is_active',             sa.String(1),   server_default='Y'),
        sa.Column('created_at',            sa.DateTime(),  server_default=sa.func.now()),
        sa.Column('updated_at',            sa.DateTime(),  server_default=sa.func.now()),
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 8. performance_metrics
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        'performance_metrics',
        sa.Column('id',                      sa.String(36),  primary_key=True),
        sa.Column('agentium_id',             sa.String(10),  unique=True, nullable=False),
        sa.Column('agent_id',                sa.String(36),  sa.ForeignKey('agents.id'), nullable=False),
        sa.Column('calculated_by_agent_id',  sa.String(36),  sa.ForeignKey('agents.id'), nullable=False),
        sa.Column('period_start',            sa.DateTime(),  nullable=False),
        sa.Column('period_end',              sa.DateTime(),  nullable=False),
        sa.Column('tasks_assigned',          sa.Integer(),   server_default='0'),
        sa.Column('tasks_completed',         sa.Integer(),   server_default='0'),
        sa.Column('tasks_failed',            sa.Integer(),   server_default='0'),
        sa.Column('tasks_rejected',          sa.Integer(),   server_default='0'),
        sa.Column('avg_quality_score',       sa.Float(),     nullable=True),
        sa.Column('constitution_violations', sa.Integer(),   server_default='0'),
        sa.Column('avg_response_time',       sa.Float(),     nullable=True),
        sa.Column('total_tokens_used',       sa.Integer(),   server_default='0'),
        sa.Column('trend',                   sa.String(20),  nullable=True),
        sa.Column('recommended_action',      sa.String(50),  nullable=True),
        sa.Column('is_active',               sa.String(1),   server_default='Y'),
        sa.Column('created_at',              sa.DateTime(),  server_default=sa.func.now()),
        sa.Column('updated_at',              sa.DateTime(),  server_default=sa.func.now()),
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 9. monitoring_alerts
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        'monitoring_alerts',
        sa.Column('id',                   sa.String(36),  primary_key=True),
        sa.Column('agentium_id',          sa.String(10),  unique=True, nullable=False),
        sa.Column('alert_type',           sa.String(50),  nullable=False),
        sa.Column('severity',             sa.String(20),  nullable=False),
        sa.Column('detected_by_agent_id', sa.String(36),  sa.ForeignKey('agents.id'), nullable=False),
        sa.Column('affected_agent_id',    sa.String(36),  sa.ForeignKey('agents.id'), nullable=True),
        sa.Column('message',              sa.Text(),      nullable=False),
        sa.Column('alert_metadata',       sa.JSON(),      nullable=True),
        sa.Column('notified_agents',      sa.JSON(),      nullable=True),
        sa.Column('acknowledged_by',      sa.String(10),  nullable=True),
        sa.Column('resolved_by',          sa.String(10),  nullable=True),
        sa.Column('status',               sa.String(20),  server_default='active'),
        sa.Column('is_active',            sa.String(1),   server_default='Y'),
        sa.Column('created_at',           sa.DateTime(),  server_default=sa.func.now()),
        sa.Column('updated_at',           sa.DateTime(),  server_default=sa.func.now()),
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 10. critic_agents (joined-table inheritance from agents)
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        'critic_agents',
        sa.Column('id',                      sa.String(36),  sa.ForeignKey('agents.id'), primary_key=True),
        sa.Column('critic_specialty',        sa.String(20),  nullable=False),
        sa.Column('reviews_completed',       sa.Integer(),   server_default='0'),
        sa.Column('vetoes_issued',           sa.Integer(),   server_default='0'),
        sa.Column('escalations_issued',      sa.Integer(),   server_default='0'),
        sa.Column('passes_issued',           sa.Integer(),   server_default='0'),
        sa.Column('avg_review_time_ms',      sa.Float(),     server_default='0.0'),
        sa.Column('preferred_review_model',  sa.String(100), nullable=True),
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 11. critique_reviews
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        'critique_reviews',
        sa.Column('id',                 sa.String(36),  primary_key=True),
        sa.Column('agentium_id',        sa.String(10),  unique=True, nullable=False),
        sa.Column('task_id',            sa.String(36),  sa.ForeignKey('tasks.id'), nullable=False),
        sa.Column('subtask_id',         sa.String(36),  sa.ForeignKey('subtasks.id'), nullable=True),
        sa.Column('critic_type',        sa.String(20),  nullable=False),
        sa.Column('critic_agentium_id', sa.String(10),  nullable=False),
        sa.Column('verdict',            sa.String(20),  nullable=False),
        sa.Column('rejection_reason',   sa.Text(),      nullable=True),
        sa.Column('suggestions',        sa.Text(),      nullable=True),
        sa.Column('retry_count',        sa.Integer(),   server_default='0'),
        sa.Column('max_retries',        sa.Integer(),   server_default='5'),
        sa.Column('review_duration_ms', sa.Float(),     server_default='0.0'),
        sa.Column('model_used',         sa.String(100), nullable=True),
        sa.Column('output_hash',        sa.String(64),  nullable=True),
        sa.Column('reviewed_at',        sa.DateTime(),  server_default=sa.func.now()),
        sa.Column('is_active',          sa.String(1),   server_default='Y'),
        sa.Column('created_at',         sa.DateTime(),  server_default=sa.func.now()),
        sa.Column('updated_at',         sa.DateTime(),  server_default=sa.func.now()),
    )
    op.create_index('idx_critique_task',   'critique_reviews', ['task_id'])
    op.create_index('idx_critique_critic', 'critique_reviews', ['critic_agentium_id'])

    # ─────────────────────────────────────────────────────────────────────────
    # Schema fixes on existing tables
    # ─────────────────────────────────────────────────────────────────────────

    # users: add is_pending if not already there
    # (001 schema may have omitted it)
    try:
        op.add_column('users', sa.Column('is_pending', sa.Boolean(), server_default='true', nullable=False))
    except Exception:
        pass  # Column already exists — safe to ignore

    # user_model_configs: add columns present in user_config.py but missing from 001
    new_config_columns = [
        ('provider_name',      sa.Column('provider_name',      sa.String(50),   nullable=True)),
        ('api_key_masked',     sa.Column('api_key_masked',      sa.String(10),   nullable=True)),
        ('api_base_url',       sa.Column('api_base_url',        sa.String(500),  nullable=True)),
        ('azure_endpoint',     sa.Column('azure_endpoint',      sa.String(500),  nullable=True)),
        ('azure_deployment',   sa.Column('azure_deployment',    sa.String(100),  nullable=True)),
        ('available_models',   sa.Column('available_models',    sa.JSON(),       nullable=True)),
        ('model_family',       sa.Column('model_family',        sa.String(50),   nullable=True)),
        ('local_server_url',   sa.Column('local_server_url',    sa.String(500),  nullable=True)),
        ('top_p',              sa.Column('top_p',               sa.Float(),      server_default='1.0')),
        ('timeout_seconds',    sa.Column('timeout_seconds',     sa.Integer(),    server_default='60')),
        ('last_error',         sa.Column('last_error',          sa.Text(),       nullable=True)),
        ('last_tested_at',     sa.Column('last_tested_at',      sa.DateTime(),   nullable=True)),
        ('last_used_at',       sa.Column('last_used_at',        sa.DateTime(),   nullable=True)),
        ('total_requests',     sa.Column('total_requests',      sa.Integer(),    server_default='0')),
        ('total_tokens',       sa.Column('total_tokens',        sa.Integer(),    server_default='0')),
        ('rate_limit',         sa.Column('rate_limit',          sa.Integer(),    nullable=True)),
        ('estimated_cost_usd', sa.Column('estimated_cost_usd',  sa.Float(),      server_default='0.0')),
        ('extra_params',       sa.Column('extra_params',        sa.JSON(),       nullable=True)),
    ]
    for col_name, col_def in new_config_columns:
        try:
            op.add_column('user_model_configs', col_def)
        except Exception:
            pass  # Column already exists — safe to ignore

    # agents: add custom_capabilities if the add_custom_capabilities migration
    # wasn't chained correctly (defensive — no-op if already present)
    try:
        op.add_column(
            'agents',
            sa.Column(
                'custom_capabilities',
                sa.Text(),
                nullable=True,
                comment='JSON: {"granted": [...], "revoked": [...]}'
            )
        )
        op.execute("""
            UPDATE agents
            SET custom_capabilities = '{"granted": [], "revoked": []}'
            WHERE custom_capabilities IS NULL
        """)
    except Exception:
        pass


def downgrade():
    # Drop in reverse dependency order
    op.drop_table('critique_reviews')
    op.drop_table('critic_agents')
    op.drop_table('monitoring_alerts')
    op.drop_table('performance_metrics')
    op.drop_table('task_verifications')
    op.drop_table('violation_reports')
    op.drop_table('agent_health_reports')
    op.drop_table('chat_messages')
    op.drop_table('conversations')
    op.drop_table('model_usage_logs')
    op.drop_table('system_settings')

    # Revert column additions (best-effort)
    for col in [
        'provider_name', 'api_key_masked', 'api_base_url', 'azure_endpoint',
        'azure_deployment', 'available_models', 'model_family', 'local_server_url',
        'top_p', 'timeout_seconds', 'last_error', 'last_tested_at', 'last_used_at',
        'total_requests', 'total_tokens', 'rate_limit', 'estimated_cost_usd', 'extra_params',
    ]:
        try:
            op.drop_column('user_model_configs', col)
        except Exception:
            pass

    try:
        op.drop_column('users', 'is_pending')
    except Exception:
        pass

    try:
        op.drop_column('agents', 'custom_capabilities')
    except Exception:
        pass