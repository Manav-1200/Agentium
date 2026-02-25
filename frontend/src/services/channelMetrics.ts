import { api } from './api';
import type { 
  ChannelMetricsResponse, 
  AllChannelsMetricsResponse,
  MessageLog 
} from '@/types';

export const channelMetricsApi = {
  // Get metrics for specific channel
  getChannelMetrics: (channelId: string) => 
    api.get<ChannelMetricsResponse>(`/api/v1/channels/${channelId}/metrics`)
      .then(r => r.data),
  
  // Get all channels metrics (for dashboard)
  getAllChannelsMetrics: () => 
    api.get<AllChannelsMetricsResponse>('/api/v1/channels/metrics')
      .then(r => r.data),
  
  // Get message logs for channel
  getChannelLogs: (channelId: string, limit = 50, offset = 0) => 
    api.get<{ messages: MessageLog[]; total: number }>(
      `/api/v1/channels/${channelId}/messages?limit=${limit}&offset=${offset}`
    ).then(r => r.data),
  
  // Reset circuit breaker
  resetChannel: (channelId: string) => 
    api.post(`/api/v1/channels/${channelId}/reset`).then(r => r.data),
};