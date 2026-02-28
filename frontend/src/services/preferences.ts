import { api } from './api';
import { UserPreference, PreferenceHistoryEntry } from '../types';

// ═══════════════════════════════════════════════════════════
// User Preferences Service
// ═══════════════════════════════════════════════════════════

export interface CreatePreferenceRequest {
    key: string;
    value: any;
    category?: string;
    scope?: string;
    scope_target_id?: string;
    description?: string;
    editable_by_agents?: boolean;
}

export interface UpdatePreferenceRequest {
    value: any;
    reason?: string;
}

export interface BulkUpdateRequest {
    preferences: Record<string, any>;
    reason?: string;
}

export interface PreferenceListResponse {
    user_id: string;
    count: number;
    preferences: UserPreference[];
}

export interface SystemDefaultsResponse {
    defaults: Record<string, any>;
    categories: Record<string, string>;
}

export interface OptimizationResult {
    duplicates_removed: number;
    unused_cleaned: number;
    history_compressed: number;
    conflicts_resolved: number;
}

export const preferencesService = {
    // ═══ User Endpoints ═══

    getPreferences: async (category?: string, scope?: string): Promise<PreferenceListResponse> => {
        const params = new URLSearchParams();
        if (category) params.append('category', category);
        if (scope) params.append('scope', scope);

        const query = params.toString() ? `?${params.toString()}` : '';
        const response = await api.get<PreferenceListResponse>(`/api/v1/preferences${query}`);
        return response.data;
    },

    getPreference: async (key: string, defaultValue?: string): Promise<{ key: string; value: any; default_used: boolean }> => {
        const params = new URLSearchParams();
        if (defaultValue !== undefined) params.append('default', defaultValue);

        const query = params.toString() ? `?${params.toString()}` : '';
        // encodeURIComponent prevents keys containing '/' or '?' from corrupting the URL path
        const response = await api.get<{ key: string; value: any; default_used: boolean }>(`/api/v1/preferences/${encodeURIComponent(key)}${query}`);
        return response.data;
    },

    createPreference: async (data: CreatePreferenceRequest): Promise<{ status: string; preference: UserPreference }> => {
        const response = await api.post<{ status: string; preference: UserPreference }>('/api/v1/preferences/', data);
        return response.data;
    },

    updatePreference: async (key: string, data: UpdatePreferenceRequest): Promise<{ status: string; preference: UserPreference }> => {
        const response = await api.put<{ status: string; preference: UserPreference }>(`/api/v1/preferences/${encodeURIComponent(key)}`, data);
        return response.data;
    },

    deletePreference: async (key: string): Promise<{ status: string; key: string }> => {
        const response = await api.delete<{ status: string; key: string }>(`/api/v1/preferences/${encodeURIComponent(key)}`);
        return response.data;
    },

    bulkUpdate: async (data: BulkUpdateRequest): Promise<{ status: string; results: { success: string[]; failed: Array<{ key: string; error: string }> } }> => {
        const response = await api.post<{ status: string; results: { success: string[]; failed: Array<{ key: string; error: string }> } }>('/api/v1/preferences/bulk', data);
        return response.data;
    },

    // ═══ System/Default Endpoints ═══

    getSystemDefaults: async (): Promise<SystemDefaultsResponse> => {
        const response = await api.get<SystemDefaultsResponse>('/api/v1/preferences/system/defaults');
        return response.data;
    },

    initializeDefaults: async (): Promise<{ status: string; count: number; preferences: UserPreference[] }> => {
        const response = await api.post<{ status: string; count: number; preferences: UserPreference[] }>('/api/v1/preferences/system/initialize');
        return response.data;
    },

    // ═══ Agent Tool Endpoints ═══

    agentListPreferences: async (category?: string, include_values?: boolean): Promise<{
        status: string;
        count: number;
        agent_tier: string;
        category_filter?: string;
        preferences: UserPreference[];
    }> => {
        const params = new URLSearchParams();
        if (category) params.append('category', category);
        if (include_values !== undefined) params.append('include_values', String(include_values));

        const query = params.toString() ? `?${params.toString()}` : '';
        const response = await api.get(`/api/v1/preferences/agent/list${query}`);
        return response.data;
    },

    agentGetPreference: async (key: string, defaultValue?: any): Promise<{
        status: string;
        key: string;
        value: any;
        editable: boolean;
    }> => {
        const params = new URLSearchParams();
        // Serialise default as JSON so objects/arrays/booleans round-trip correctly
        if (defaultValue !== undefined) params.append('default', JSON.stringify(defaultValue));

        const query = params.toString() ? `?${params.toString()}` : '';
        const response = await api.get(`/api/v1/preferences/agent/get/${encodeURIComponent(key)}${query}`);
        return response.data;
    },

    agentSetPreference: async (key: string, value: any, reason?: string): Promise<{
        status: string;
        key: string;
        value: any;
        message: string;
    }> => {
        // Send as a JSON body rather than query params — passing complex values (objects,
        // arrays, booleans) through URLSearchParams via axios `params` corrupts them to
        // "[object Object]" or stringified primitives the server may not parse correctly.
        const response = await api.post(`/api/v1/preferences/agent/set/${encodeURIComponent(key)}`, {
            value,
            ...(reason !== undefined && { reason }),
        });
        return response.data;
    },

    // ═══ Admin/Optimization Endpoints ═══

    optimizePreferences: async (): Promise<{ status: string; results: OptimizationResult }> => {
        const response = await api.post<{ status: string; results: OptimizationResult }>('/api/v1/preferences/admin/optimize');
        return response.data;
    },

    getOptimizationRecommendations: async (): Promise<{
        count: number;
        recommendations: Array<{
            type: string;
            key: string;
            recommendation: string;
            details?: Record<string, any>;
        }>;
    }> => {
        const response = await api.get('/api/v1/preferences/admin/recommendations');
        return response.data;
    },

    getPreferenceHistory: async (preferenceId: string, limit?: number): Promise<{
        preference_id: string;
        count: number;
        history: PreferenceHistoryEntry[];
    }> => {
        const params = new URLSearchParams();
        if (limit) params.append('limit', String(limit));

        const query = params.toString() ? `?${params.toString()}` : '';
        const response = await api.get(`/api/v1/preferences/admin/history/${encodeURIComponent(preferenceId)}${query}`);
        return response.data;
    },
};

// ═══════════════════════════════════════════════════════════
// Preference Categories Helper
// ═══════════════════════════════════════════════════════════

export const PREFERENCE_CATEGORIES = [
    { id: 'general', name: 'General', description: 'General system preferences', icon: 'Settings' },
    { id: 'ui', name: 'UI', description: 'User interface settings', icon: 'Layout' },
    { id: 'notifications', name: 'Notifications', description: 'Notification preferences', icon: 'Bell' },
    { id: 'agents', name: 'Agents', description: 'Agent behavior settings', icon: 'Users' },
    { id: 'tasks', name: 'Tasks', description: 'Task execution preferences', icon: 'CheckSquare' },
    { id: 'chat', name: 'Chat', description: 'Chat and messaging settings', icon: 'MessageSquare' },
    { id: 'models', name: 'Models', description: 'AI model configuration', icon: 'Brain' },
    { id: 'tools', name: 'Tools', description: 'Tool execution settings', icon: 'Wrench' },
    { id: 'privacy', name: 'Privacy', description: 'Privacy and data settings', icon: 'Shield' },
    { id: 'custom', name: 'Custom', description: 'Custom user-defined preferences', icon: 'Pencil' },
] as const;

export type PreferenceCategoryId = typeof PREFERENCE_CATEGORIES[number]['id'];

// ═══════════════════════════════════════════════════════════
// Data Type Helpers
// ═══════════════════════════════════════════════════════════

export const DATA_TYPE_LABELS: Record<string, { label: string; color: string }> = {
    string: { label: 'Text', color: 'blue' },
    integer: { label: 'Number', color: 'green' },
    float: { label: 'Decimal', color: 'cyan' },
    boolean: { label: 'Yes/No', color: 'purple' },
    json: { label: 'JSON', color: 'orange' },
    array: { label: 'List', color: 'pink' },
};

// Helper to format preference value for display
export const formatPreferenceValue = (value: any, dataType: string): string => {
    if (value === null || value === undefined) return '—';

    switch (dataType) {
        case 'boolean':
            return value ? 'Yes' : 'No';
        case 'array':
        case 'json':
            return JSON.stringify(value);
        case 'integer':
        case 'float':
            return String(value);
        default:
            return String(value);
    }
};

// Helper to parse input value based on data type
export const parsePreferenceValue = (input: string, dataType: string): any => {
    switch (dataType) {
        case 'boolean':
            return input.toLowerCase() === 'true' || input === '1' || input === 'yes';
        case 'integer':
            return parseInt(input, 10);
        case 'float':
            return parseFloat(input);
        case 'array':
        case 'json':
            try {
                return JSON.parse(input);
            } catch {
                return input;
            }
        default:
            return input;
    }
};