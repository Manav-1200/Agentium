import { api } from './api';
import { Task } from '../types';

export interface CreateTaskRequest {
    title: string;
    description: string;
    priority: string;
    task_type: string;
    constitutional_basis?: string;
    hierarchical_id?: string;
    parent_task_id?: string;
}

export const tasksService = {
    getTasks: async (filters?: { status?: string; agent_id?: string; parent_task_id?: string }): Promise<Task[]> => {
        const params = new URLSearchParams();
        if (filters?.status) params.append('status', filters.status);
        if (filters?.agent_id) params.append('agent_id', filters.agent_id);
        if (filters?.parent_task_id) params.append('parent_task_id', filters.parent_task_id);

        const query = params.toString() ? `?${params.toString()}` : '';
        const response = await api.get<Task[]>(`/api/v1/tasks/${query}`);

        return Array.isArray(response.data)
            ? response.data
            : (response.data as any).tasks ?? [];
    },

    createTask: async (data: CreateTaskRequest): Promise<Task> => {
        const response = await api.post<Task>('/api/v1/tasks/', data);
        return response.data;
    },

    executeTask: async (taskId: string, agentId: string): Promise<any> => {
        const response = await api.post(`/api/v1/tasks/${taskId}/execute?agent_id=${agentId}`);
        return response.data;
    },

    escalateTask: async (taskId: string, reason: string): Promise<any> => {
        const response = await api.post(`/api/v1/tasks/${taskId}/escalate?reason=${encodeURIComponent(reason)}`);
        return response.data;
    },

    retryTask: async (taskId: string): Promise<any> => {
        const response = await api.post(`/api/v1/tasks/${taskId}/retry`);
        return response.data;
    },

    getTaskEvents: async (taskId: string): Promise<any> => {
        const response = await api.get(`/api/v1/tasks/${taskId}/events`);
        return response.data;
    },

    getTaskSubtasks: async (taskId: string): Promise<any> => {
        const response = await api.get(`/api/v1/tasks/${taskId}/subtasks`);
        return response.data;
    },
};

// ─── Critic service calls ─────────────────────────────────────────────────────

export const criticsService = {
    getStats: async () => {
        const response = await api.get('/api/v1/critics/stats');
        return response.data;
    },

    getTaskReviews: async (taskId: string) => {
        const response = await api.get(`/api/v1/critics/reviews/${taskId}`);
        return response.data;
    },

    submitReview: async (payload: {
        task_id: string;
        output_content: string;
        critic_type: 'code' | 'output' | 'plan';
        subtask_id?: string;
        retry_count?: number;
    }) => {
        const response = await api.post('/api/v1/critics/review', payload);
        return response.data;
    },
};