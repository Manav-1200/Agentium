import { api } from './api';
import { Agent } from '../types';

export interface SpawnAgentRequest {
    child_type: 'council_member' | 'lead_agent' | 'task_agent';
    name: string;
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
        const response = await api.post<{ agent: Agent }>(`/api/v1/agents/lifecycle/spawn?child_type=${data.child_type}&name=${encodeURIComponent(data.name)}`);
        return response.data.agent;
    },

    terminateAgent: async (id: string, reason: string): Promise<void> => {
        await api.post(`/api/v1/agents/lifecycle/${id}/terminate?reason=${encodeURIComponent(reason)}`);
    }
};