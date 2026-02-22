import { api } from './api';

export interface UnifiedConversation {
    id: string;
    title: string;
    user_id: string;
    is_active: boolean;
    is_archived: string;
    is_deleted: string;
    context?: string;
    created_at: string;
    updated_at: string;
    last_message_at?: string;
    messages?: UnifiedMessage[];
}

export interface UnifiedMessage {
    id: string;
    role: string;
    content: string;
    conversation_id: string;
    user_id: string;
    external_message_id?: string;
    sender_channel?: string;
    message_type: string;
    media_url?: string;
    attachments?: any;
    metadata?: any;
    is_deleted: string;
    created_at: string;
}

export interface InboxConversationsResponse {
    conversations: UnifiedConversation[];
    total: number;
}

export const inboxApi = {
    getConversations: async (status?: string, channel?: string): Promise<InboxConversationsResponse> => {
        const params = new URLSearchParams();
        if (status) params.append('status', status);
        if (channel) params.append('channel', channel);

        const response = await api.get(`/api/v1/inbox/conversations?${params.toString()}`);
        return response.data;
    },

    getConversation: async (id: string): Promise<UnifiedConversation> => {
        const response = await api.get(`/api/v1/inbox/conversations/${id}`);
        return response.data;
    },

    reply: async (conversationId: string, content: string, attachments?: any[]): Promise<any> => {
        const response = await api.post(`/api/v1/inbox/conversations/${conversationId}/reply`, {
            content,
            message_type: 'text',
            attachments
        });
        return response.data;
    }
};
