import { api } from './api';
import { Agent } from '../types';

export interface PromoteAgentRequest {
    task_agentium_id: string;
    promoted_by_agentium_id: string;
    reason: string;
}

export interface PromotionResult {
    success: boolean;
    old_agentium_id: string;
    new_agentium_id: string;
    promoted_by: string;
    reason: string;
    tasks_transferred: number;
    message: string;
}

export interface CapacityTier {
    used: number;
    available: number;
    total: number;
    percentage: number;
    warning: boolean;
    critical: boolean;
}

export interface CapacityData {
    head: CapacityTier;
    council: CapacityTier;
    lead: CapacityTier;
    task: CapacityTier;
    warnings: string[];
}

export interface LifecycleStats {
    period_days: number;
    lifecycle_events: {
        spawned: number;
        promoted: number;
        liquidated: number;
        reincarnated: number;
    };
    active_agents_by_tier: {
        tier_0: number;
        tier_1: number;
        tier_2: number;
        tier_3: number;
    };
    capacity: {
        head: CapacityTier;
        council: CapacityTier;
        lead: CapacityTier;
        task: CapacityTier;
    };
}

export interface BulkLiquidateDryRunResult {
    dry_run: true;
    idle_agents_found: number;
    idle_agents: { agentium_id: string; name: string; idle_days: number }[];
    message: string;
}

export interface BulkLiquidateResult {
    dry_run: false;
    liquidated_count: number;
    liquidated: { agentium_id: string; name: string }[];
    skipped_count: number;
    skipped: { agentium_id: string; reason: string }[];
    message: string;
}

export interface SpawnAgentRequest {
    child_type: 'council_member' | 'lead_agent' | 'task_agent';
    name: string;
    description: string;
    parent_agentium_id: string;
}

export const agentsService = {
    getAgents: async (filters?: { type?: string; status?: string }): Promise<Agent[]> => {
        const params = new URLSearchParams();
        if (filters?.type) params.append('agent_type', filters.type);
        if (filters?.status) params.append('status', filters.status);

        const response = await api.get<{ agents: Agent[] }>(`/api/v1/agents?${params.toString()}`);
        return response.data.agents;
    },

    getAgent: async (id: string): Promise<Agent> => {
        const response = await api.get<Agent>(`/api/v1/agents/${id}`);
        return response.data;
    },

    spawnAgent: async (parentId: string, data: SpawnAgentRequest): Promise<Agent> => {
        // Backend has two separate spawn endpoints: /spawn/task and /spawn/lead.
        // task_agent -> POST /spawn/task  (parent must be Lead 2xxxx or Council 1xxxx)
        // lead_agent / council_member -> POST /spawn/lead  (parent must be Council 1xxxx or Head 0xxxx)
        const endpoint = data.child_type === 'task_agent'
            ? '/api/v1/agents/lifecycle/spawn/task'
            : '/api/v1/agents/lifecycle/spawn/lead';

        const response = await api.post<{ agent: Agent }>(endpoint, {
            parent_agentium_id: data.parent_agentium_id,
            name: data.name,
            description: data.description,
        });
        return response.data.agent;
    },

    terminateAgent: async (id: string, reason: string, authorizedById: string): Promise<void> => {
        // Backend uses "liquidate" (not terminate) — POST /liquidate does full cleanup:
        // cancels tasks, notifies child agents, revokes capabilities.
        await api.post('/api/v1/agents/lifecycle/liquidate', {
            target_agentium_id: id,
            liquidated_by_agentium_id: authorizedById,
            reason,
            force: false,
        });
    }
};

export const lifecycleService = {
    /**
     * Promote a Task Agent (3xxxx) to Lead Agent (2xxxx).
     * promoted_by must be Council (1xxxx) or Head (0xxxx).
     */
    promoteAgent: async (data: PromoteAgentRequest): Promise<PromotionResult> => {
        const response = await api.post<PromotionResult>(
            '/api/v1/agents/lifecycle/promote',
            data,
        );
        return response.data;
    },

    /**
     * Bulk-liquidate idle agents.
     * @param idleDaysThreshold  Days without activity to consider idle (default 7)
     * @param dryRun             When true, only detects — does NOT liquidate
     */
    bulkLiquidateIdle: async (
        idleDaysThreshold = 7,
        dryRun = true,
    ): Promise<BulkLiquidateDryRunResult | BulkLiquidateResult> => {
        const params = new URLSearchParams({
            idle_days_threshold: String(idleDaysThreshold),
            dry_run: String(dryRun),
        });
        const response = await api.post<BulkLiquidateDryRunResult | BulkLiquidateResult>(
            `/api/v1/agents/lifecycle/bulk/liquidate-idle?${params}`,
        );
        return response.data;
    },

    /** Get ID-pool capacity for each agent tier. */
    getCapacity: async (): Promise<CapacityData> => {
        const response = await api.get<CapacityData>('/api/v1/agents/lifecycle/capacity');
        return response.data;
    },

    /** Get 30-day lifecycle event stats and active-agent counts by tier. */
    getLifecycleStats: async (): Promise<LifecycleStats> => {
        const response = await api.get<LifecycleStats>('/api/v1/agents/lifecycle/stats/lifecycle');
        return response.data;
    },
};

export interface ReassignAgentRequest {
    new_parent_id: string;
    reason?: string;
}

export interface CapabilityProfile {
    tier: string;
    agentium_id: string;
    base_capabilities: string[];
    granted_capabilities: string[];
    revoked_capabilities: string[];
    effective_capabilities: string[];
    total_count: number;
}

export const capabilitiesService = {
    getAgentCapabilities: async (agentiumId: string): Promise<CapabilityProfile> => {
        const response = await api.get<CapabilityProfile>(`/api/v1/capabilities/agent/${agentiumId}`);
        return response.data;
    },

    checkCapability: async (agentiumId: string, capability: string): Promise<boolean> => {
        const response = await api.post<{ has_capability: boolean }>('/api/v1/capabilities/check', {
            agentium_id: agentiumId,
            capability,
        });
        return response.data.has_capability;
    },

    validateReassignment: async (agentiumId: string, newParentId: string): Promise<{ valid: boolean; reason?: string }> => {
        // An agent can be reassigned if its type is compatible with the new parent's tier.
        // task_agent -> lead_agent (tier 2)
        // lead_agent -> council_member (tier 1) or head_of_council (tier 0)
        // We validate by checking spawn capability on new parent.
        const agentTier = agentiumId[0];
        const parentTier = newParentId[0];

        const capabilityNeeded =
            agentTier === '3' ? 'spawn_task_agent' :
            agentTier === '2' ? 'spawn_lead' :
            agentTier === '1' ? 'spawn_lead' : null;

        if (!capabilityNeeded) return { valid: false, reason: 'Head of Council cannot be reassigned.' };
        if (parentTier >= agentTier) return { valid: false, reason: 'New parent must outrank the agent.' };

        const hasCapability = await capabilitiesService.checkCapability(newParentId, capabilityNeeded);
        return hasCapability
            ? { valid: true }
            : { valid: false, reason: `New parent lacks '${capabilityNeeded}' capability.` };
    },
};

// Add reassign to agentsService
Object.assign(agentsService, {
    reassignAgent: async (agentId: string, data: ReassignAgentRequest): Promise<Agent> => {
        const response = await api.post<{ agent: Agent }>(
            `/api/v1/agents/lifecycle/${agentId}/reassign`,
            data
        );
        return response.data.agent;
    },
});