export interface User {
    id: string;
    username: string;
    role: 'sovereign' | 'admin';
    isAuthenticated: boolean;
}

export interface BackendStatus {
    status: 'connected' | 'disconnected' | 'connecting';
    version?: string;
    lastChecked: Date;
    latency?: number;
}

export interface ModelConfig {
    id: string;
    provider: 'openai' | 'anthropic' | 'gemini' | 'local' | 'azure' | 'custom';
    config_name: string;
    default_model: string;
    available_models: string[];
    status: 'active' | 'inactive' | 'error' | 'testing';
    is_default: boolean;
    settings: {
        max_tokens: number;
        temperature: number;
        timeout: number;
    };
    local_config?: {
        model_path?: string;
        server_url?: string;
    };
    usage: {
        tokens_total: number;
        requests: number;
    };
    last_tested?: string;
}

export interface Agent {
    id: string;
    agentium_id: string;
    agent_type: 'head_of_council' | 'council_member' | 'lead_agent' | 'task_agent';
    name: string;
    status: 'initializing' | 'active' | 'deliberating' | 'working' | 'suspended' | 'terminated';
    model_config?: {
        config_id: string;
        config_name: string;
        provider: string;
        model: string;
    };
    parent?: string;
    subordinates: string[];
    stats: {
        tasks_completed: number;
        tasks_failed: number;
    };
    current_task?: string;
    constitution_version: string;
    is_terminated: boolean;
}

export interface Task {
    id: string;
    agentium_id: string;
    title: string;
    description: string;
    status: string;
    priority: string;
    progress: number;
    created_by: string;
    assigned_agents: {
        head?: string;
        lead?: string;
        task_agents: string[];
    };
    created_at: string;
}

export interface Constitution {
    id: string;
    version: string;
    preamble: string;
    articles: Record<string, string>;
    prohibited_actions: string[];
    sovereign_preferences: Record<string, any>;
    effective_date: string;
}