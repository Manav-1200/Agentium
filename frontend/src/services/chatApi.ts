/**
 * Chat history and conversation management API.
 */

import { api } from './api';

export interface ChatMessage {
    id: string;
    conversation_id?: string;
    user_id: string;
    role: 'sovereign' | 'head_of_council' | 'system';
    content: string;
    attachments?: Array<{
        name: string;
        type: string;
        size: number;
        url: string;
        category: string;
    }>;
    metadata?: {
        agent_id?: string;
        model?: string;
        tokens_used?: number;
        task_created?: boolean;
        task_id?: string;
        latency_ms?: number;
    };
    agent_id?: string;
    created_at: string;
}

export interface Conversation {
    id: string;
    user_id: string;
    title?: string;
    context?: string;
    created_at: string;
    updated_at: string;
    last_message_at: string;
    message_count: number;
    messages?: ChatMessage[];
}

export interface ConversationListResponse {
    conversations: Conversation[];
    total: number;
}

export interface ChatHistoryResponse {
    messages: ChatMessage[];
    total: number;
    has_more: boolean;
    next_cursor?: string;
}

const API_BASE = '/api/v1/chat';

export const chatApi = {
    /**
     * Get chat history (legacy endpoint).
     */
    getHistory: async (limit: number = 50): Promise<ChatHistoryResponse> => {
        const response = await api.get<ChatHistoryResponse>(`${API_BASE}/history?limit=${limit}`);
        return response.data;
    },

    /**
     * List all conversations for current user.
     */
    listConversations: async (): Promise<ConversationListResponse> => {
        const response = await api.get<ConversationListResponse>(`${API_BASE}/conversations`);
        return response.data;
    },

    /**
     * Get a specific conversation with messages.
     */
    getConversation: async (conversationId: string): Promise<Conversation> => {
        const response = await api.get<Conversation>(`${API_BASE}/conversations/${conversationId}`);
        return response.data;
    },

    /**
     * Create a new conversation.
     */
    createConversation: async (title?: string, context?: string): Promise<Conversation> => {
        const response = await api.post<Conversation>(`${API_BASE}/conversations`, {
            title,
            context
        });
        return response.data;
    },

    /**
     * Update conversation metadata.
     */
    updateConversation: async (conversationId: string, updates: { title?: string; context?: string }): Promise<Conversation> => {
        const response = await api.put<Conversation>(`${API_BASE}/conversations/${conversationId}`, updates);
        return response.data;
    },

    /**
     * Delete a conversation (soft delete).
     */
    deleteConversation: async (conversationId: string): Promise<{ success: boolean }> => {
        const response = await api.delete(`${API_BASE}/conversations/${conversationId}`);
        return response.data;
    },

    /**
     * Archive a conversation.
     */
    archiveConversation: async (conversationId: string): Promise<{ success: boolean }> => {
        const response = await api.post(`${API_BASE}/conversations/${conversationId}/archive`);
        return response.data;
    },

    /**
     * Search messages.
     */
    searchMessages: async (query: string, limit: number = 20): Promise<ChatHistoryResponse> => {
        const response = await api.get<ChatHistoryResponse>(`${API_BASE}/search?q=${encodeURIComponent(query)}&limit=${limit}`);
        return response.data;
    },

    /**
     * Delete a specific message.
     */
    deleteMessage: async (messageId: string): Promise<{ success: boolean }> => {
        const response = await api.delete(`${API_BASE}/messages/${messageId}`);
        return response.data;
    },

    /**
     * Get conversation statistics.
     */
    getStats: async (): Promise<{
        total_conversations: number;
        total_messages: number;
        messages_today: number;
        storage_used_bytes: number;
    }> => {
        const response = await api.get(`${API_BASE}/stats`);
        return response.data;
    },

    /**
     * Export conversation to file.
     */
    exportConversation: async (conversationId: string, format: 'json' | 'markdown' | 'txt' = 'json'): Promise<Blob> => {
        const response = await api.get(`${API_BASE}/conversations/${conversationId}/export?format=${format}`, {
            responseType: 'blob'
        });
        return response.data;
    }
};

export default chatApi;