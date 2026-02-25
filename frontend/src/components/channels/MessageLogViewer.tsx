import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { channelMetricsApi } from '@/services/channelMetrics';
import { format } from 'date-fns';
import { CheckCircle, XCircle, Clock, AlertTriangle } from 'lucide-react';

interface MessageLogViewerProps {
  channelId: string;
}

export function MessageLogViewer({ channelId }: MessageLogViewerProps) {
  const [limit] = useState(50);
  
  const { data, isLoading } = useQuery({
    queryKey: ['channel-logs', channelId],
    queryFn: () => channelMetricsApi.getChannelLogs(channelId, limit),
  });

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'responded': return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'failed': return <XCircle className="w-4 h-4 text-red-500" />;
      case 'processing': return <Clock className="w-4 h-4 text-yellow-500 animate-spin" />;
      default: return <AlertTriangle className="w-4 h-4 text-gray-400" />;
    }
  };

  if (isLoading) return <div className="text-sm text-gray-500">Loading logs...</div>;

  return (
    <div className="border border-gray-200 dark:border-[#1e2535] rounded-xl overflow-hidden">
      <div className="bg-gray-50 dark:bg-[#0f1117] px-4 py-2 border-b border-gray-200 dark:border-[#1e2535]">
        <h4 className="text-sm font-semibold text-gray-900 dark:text-white">Recent Messages</h4>
      </div>
      <div className="max-h-64 overflow-y-auto">
        {data?.messages.length === 0 ? (
          <div className="p-4 text-sm text-gray-500 text-center">No messages yet</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-[#0f1117] text-xs text-gray-500">
              <tr>
                <th className="px-4 py-2 text-left">Status</th>
                <th className="px-4 py-2 text-left">Sender</th>
                <th className="px-4 py-2 text-left">Content</th>
                <th className="px-4 py-2 text-left">Time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-[#1e2535]">
              {data?.messages.map((msg) => (
                <tr key={msg.id} className="hover:bg-gray-50 dark:hover:bg-[#0f1117]">
                  <td className="px-4 py-2">{getStatusIcon(msg.status)}</td>
                  <td className="px-4 py-2 text-gray-900 dark:text-gray-100">{msg.sender_name || msg.sender_id}</td>
                  <td className="px-4 py-2 text-gray-600 dark:text-gray-400 truncate max-w-xs">
                    {msg.content}
                  </td>
                  <td className="px-4 py-2 text-xs text-gray-400">
                    {format(new Date(msg.created_at), 'MMM d, HH:mm')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}