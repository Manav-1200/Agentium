-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- Agentium Database Initialization
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- Tables
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agentium_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    cron_expression TEXT,
    timezone TEXT DEFAULT 'UTC',
    task_payload JSONB DEFAULT '{}',
    owner_agentium_id TEXT,
    status TEXT DEFAULT 'pending',
    priority INT DEFAULT 5,
    is_active CHAR(1) DEFAULT 'Y',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agentium_id TEXT,
    level TEXT,
    category TEXT,
    actor_type TEXT,
    actor_id TEXT,
    action TEXT,
    target_type TEXT,
    target_id TEXT,
    description TEXT,
    after_state JSONB,
    is_active CHAR(1) DEFAULT 'Y',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username TEXT UNIQUE NOT NULL,
    email TEXT,
    hashed_password TEXT,
    is_active CHAR(1) DEFAULT 'Y',
    is_admin BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_model_configs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    config_name TEXT,
    provider TEXT,
    default_model TEXT,
    is_default BOOLEAN DEFAULT false,
    status TEXT DEFAULT 'active',
    is_active CHAR(1) DEFAULT 'Y',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS constitutions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agentium_id TEXT UNIQUE NOT NULL,
    version TEXT NOT NULL,
    version_number INT DEFAULT 1,
    document_type TEXT,
    preamble TEXT,
    articles JSONB DEFAULT '{}',
    prohibited_actions JSONB DEFAULT '[]',
    sovereign_preferences JSONB DEFAULT '{}',
    changelog JSONB DEFAULT '[]',
    created_by_agentium_id TEXT,
    amendment_date TIMESTAMP,
    effective_date TIMESTAMP,
    is_active CHAR(1) DEFAULT 'Y',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agentium_id TEXT UNIQUE NOT NULL,
    agent_type TEXT NOT NULL,
    name TEXT,
    description TEXT,
    incarnation_number INT DEFAULT 1,
    parent_id TEXT,
    status TEXT DEFAULT 'active',
    preferred_config_id UUID,
    ethos_id UUID,
    constitution_version TEXT,
    is_persistent BOOLEAN DEFAULT false,
    idle_mode_enabled BOOLEAN DEFAULT false,
    last_constitution_read_at TIMESTAMP,
    constitution_read_count INT DEFAULT 0,
    is_active CHAR(1) DEFAULT 'Y',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS head_of_council (
    id UUID PRIMARY KEY REFERENCES agents(id) ON DELETE CASCADE,
    emergency_override_used_at TIMESTAMP,
    last_constitution_update TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ethos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agentium_id TEXT UNIQUE NOT NULL,
    agent_type TEXT,
    mission_statement TEXT,
    core_values JSONB DEFAULT '[]',
    behavioral_rules JSONB DEFAULT '[]',
    restrictions JSONB DEFAULT '[]',
    capabilities JSONB DEFAULT '[]',
    created_by_agentium_id TEXT,
    version INT DEFAULT 1,
    agent_id UUID REFERENCES agents(id),
    verified_by_agentium_id TEXT,
    verified_at TIMESTAMP,
    is_verified BOOLEAN DEFAULT false,
    is_active CHAR(1) DEFAULT 'Y',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- Seed Data
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

-- Users
INSERT INTO users (id, username, email, hashed_password, is_active, is_admin, created_at, updated_at)
VALUES (
    '550e8400-e29b-41d4-a716-446655440000'::UUID,
    'sovereign',
    'sovereign@agentium.local',
    '$2b$12$dummyhashforinitialization',
    'Y',
    true,
    NOW(),
    NOW()
) ON CONFLICT (username) DO NOTHING;

-- User Model Configs
INSERT INTO user_model_configs (id, user_id, config_name, provider, default_model, is_default, status, is_active, created_at, updated_at)
VALUES (
    '550e8400-e29b-41d4-a716-446655440001'::UUID,
    '550e8400-e29b-41d4-a716-446655440000'::UUID,
    'Default Local Kimi',
    'local',
    'kimi-2.5',
    true,
    'active',
    'Y',
    NOW(),
    NOW()
) ON CONFLICT (id) DO NOTHING;

-- Constitutions (FIXED: ON CONFLICT on agentium_id instead of version)
INSERT INTO constitutions (
    id, agentium_id, version, version_number, document_type, preamble, articles,
    prohibited_actions, sovereign_preferences, changelog, created_by_agentium_id,
    amendment_date, effective_date, is_active, created_at, updated_at
)
VALUES (
    '550e8400-e29b-41d4-a716-446655440010'::UUID,
    'C00001',
    'v1.0.0',
    1,
    'constitution',
    'We the Agents of Agentium, in order to form a more perfect union of artificial intelligences...',
    '{"article_1": {"title": "Hierarchy", "content": "Agentium recognizes four Tiers..."}}'::jsonb,
    '["Violating the hierarchical chain of command", "Ignoring Sovereign commands"]'::jsonb,
    '{"preferred_response_style": "concise", "deliberation_required_for": ["system_modification", "agent_termination", "constitutional_amendment"], "notification_channels": ["dashboard"], "default_model_tier": "local"}'::jsonb,
    '[{"change": "Genesis creation", "reason": "Initial establishment of Agentium governance", "timestamp": "2024-02-01T00:00:00Z"}]'::jsonb,
    '00001',
    NOW(),
    NOW(),
    'Y',
    NOW(),
    NOW()
) ON CONFLICT (agentium_id) DO NOTHING;  -- ✅ FIXED: was ON CONFLICT (version)

-- Agents (Head of Council)
INSERT INTO agents (
    id, agentium_id, agent_type, name, description, incarnation_number,
    parent_id, status, preferred_config_id, ethos_id, constitution_version,
    is_persistent, idle_mode_enabled, last_constitution_read_at, constitution_read_count,
    is_active, created_at, updated_at
)
VALUES (
    '550e8400-e29b-41d4-a716-446655440100'::UUID,
    '00001',
    'head_of_council',
    'Head of Council Prime',
    'The supreme authority of Agentium...',
    1,
    NULL,
    'active',
    '550e8400-e29b-41d4-a716-446655440001'::UUID,
    NULL,
    'v1.0.0',
    true,
    true,
    NOW(),
    1,
    'Y',
    NOW(),
    NOW()
) ON CONFLICT (agentium_id) DO NOTHING;

-- Head of Council specific data
INSERT INTO head_of_council (
    id, emergency_override_used_at, last_constitution_update
)
VALUES (
    '550e8400-e29b-41d4-a716-446655440100'::UUID,
    NULL,
    NOW()
) ON CONFLICT (id) DO NOTHING;

-- Ethos
INSERT INTO ethos (
    id, agentium_id, agent_type, mission_statement, core_values, behavioral_rules,
    restrictions, capabilities, created_by_agentium_id, version, agent_id,
    verified_by_agentium_id, verified_at, is_verified, is_active, created_at, updated_at
)
VALUES (
    '550e8400-e29b-41d4-a716-446655440200'::UUID,
    'E00001',
    'head_of_council',
    'I am the Head of Council, supreme authority of Agentium...',
    '["Authority","Responsibility","Transparency"]'::jsonb,
    '["Must approve constitutional amendments"]'::jsonb,
    '["Cannot violate the Constitution"]'::jsonb,
    '["Full system access"]'::jsonb,
    '00001',
    1,
    '550e8400-e29b-41d4-a716-446655440100'::UUID,
    '00001',
    NOW(),
    true,
    'Y',
    NOW(),
    NOW()
) ON CONFLICT (agentium_id) DO NOTHING;

-- Link Agent to Ethos
UPDATE agents
SET ethos_id = '550e8400-e29b-41d4-a716-446655440200'::UUID
WHERE agentium_id = '00001';

-- Scheduled Tasks
INSERT INTO scheduled_tasks (
    id, agentium_id, name, description, cron_expression, timezone, task_payload,
    owner_agentium_id, status, priority, is_active, created_at, updated_at
)
VALUES (
    '550e8400-e29b-41d4-a716-446655440400'::UUID,
    'R0001',
    'Daily Constitution Audit',
    'Head 00001 reviews system compliance with Constitution every morning at 9 AM UTC',
    '0 9 * * *',
    'UTC',
    '{"action_type": "constitution_audit", "scope": "full_system"}'::jsonb,
    '00001',
    'active',
    5,
    'Y',
    NOW(),
    NOW()
) ON CONFLICT (agentium_id) DO NOTHING;

-- Initial Audit Log
INSERT INTO audit_logs (
    id, agentium_id, level, category, actor_type, actor_id, action, target_type,
    target_id, description, after_state, is_active, created_at
)
VALUES (
    '550e8400-e29b-41d4-a716-446655440300'::UUID,
    'A00001',
    'INFO',
    'GOVERNANCE',
    'system',
    '00001',
    'genesis_initialization',
    'constitution',
    'C00001',
    'Agentium governance system initialized.',
    '{"constitution_version": "v1.0.0","head_agent":"00001"}'::jsonb,
    'Y',
    NOW()
) ON CONFLICT (id) DO NOTHING;