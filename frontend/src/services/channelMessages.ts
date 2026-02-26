import { api } from './api';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface ChannelMessage {
  id: string;
  channel_id: string;
  channel_name: string;
  channel_type: string;
  sender_id: string;
  sender_name: string | null;
  content: string;
  message_type: string;
  status: 'received' | 'processing' | 'responded' | 'failed';
  error_count: number;
  last_error: string | null;
  task_id: string | null;
  assigned_agent_id: string | null;
  media_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface MessageLogFilters {
  channel_id?: string;
  channel_type?: string;
  agent_id?: string;
  status?: string;
  success?: boolean;
  date_from?: string;
  date_to?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

export interface MessageLogResponse {
  messages: ChannelMessage[];
  total: number;
  limit: number;
  offset: number;
  stats: {
    total_in_filter: number;
    has_more: boolean;
  };
}

export interface ReplayResponse {
  success: boolean;
  message_id: string;
  new_status: string;
  detail: string;
}

export interface BulkReplayResponse {
  success: boolean;
  queued: number;
  detail: string;
}

// ─── API calls ────────────────────────────────────────────────────────────────

export const channelMessagesApi = {
  /**
   * Fetch cross-channel message log with optional filters.
   */
  getLog: async (filters: MessageLogFilters = {}): Promise<MessageLogResponse> => {
    const params = new URLSearchParams();
    if (filters.channel_id)   params.set('channel_id', filters.channel_id);
    if (filters.channel_type) params.set('channel_type', filters.channel_type);
    if (filters.agent_id)     params.set('agent_id', filters.agent_id);
    if (filters.status)       params.set('status', filters.status);
    if (filters.success !== undefined) params.set('success', String(filters.success));
    if (filters.date_from)    params.set('date_from', filters.date_from);
    if (filters.date_to)      params.set('date_to', filters.date_to);
    if (filters.search)       params.set('search', filters.search);
    params.set('limit',  String(filters.limit  ?? 50));
    params.set('offset', String(filters.offset ?? 0));

    const { data } = await api.get<MessageLogResponse>(
      `/api/v1/channels/messages/log?${params.toString()}`
    );
    return data;
  },

  /**
   * Replay a single failed message.
   */
  replayMessage: async (messageId: string): Promise<ReplayResponse> => {
    const { data } = await api.post<ReplayResponse>(
      `/channels/messages/${messageId}/replay`
    );
    return data;
  },

  /**
   * Bulk replay all failed messages, optionally for a single channel.
   */
  replayFailed: async (channelId?: string, limit = 50): Promise<BulkReplayResponse> => {
    const { data } = await api.post<BulkReplayResponse>(
      '/channels/messages/replay-failed',
      { channel_id: channelId ?? null, limit }
    );
    return data;
  },
};