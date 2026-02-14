import { useState } from 'react';
import { Smartphone, Slack, Mail, MessageCircle, User } from 'lucide-react';
import { format } from 'date-fns';

interface UnifiedMessage {
    id: string;
    channel: 'whatsapp' | 'slack' | 'email' | 'telegram';
    channelName: string;
    sender: string;
    content: string;
    timestamp: Date;
    status: 'pending' | 'processing' | 'responded';
    assignedAgent?: string;
    response?: string;
}

export function UnifiedInbox() {
    const [messages] = useState<UnifiedMessage[]>([
        {
            id: '1',
            channel: 'whatsapp',
            channelName: 'Support WhatsApp',
            sender: '+1-555-0199',
            content: 'I need help analyzing this dataset',
            timestamp: new Date(),
            status: 'processing',
            assignedAgent: '20001'
        }
    ]);
    const [filter, setFilter] = useState('all');

    const getChannelIcon = (channel: string) => {
        switch (channel) {
            case 'whatsapp': return Smartphone;
            case 'slack': return Slack;
            case 'email': return Mail;
            case 'telegram': return MessageCircle;
            default: return MessageCircle;
        }
    };

    const getStatusColor = (status: string) => {
        const colors: Record<string, string> = {
            pending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300',
            processing: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300',
            responded: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
        };
        return colors[status] || 'bg-gray-100 text-gray-800';
    };

    return (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
            <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
                <h3 className="font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                    <MessageCircle className="w-5 h-5 text-blue-600" />
                    Unified Inbox (Cross-Channel)
                </h3>
                <div className="flex gap-2">
                    {['all', 'whatsapp', 'slack', 'email'].map((f) => (
                        <button
                            key={f}
                            onClick={() => setFilter(f)}
                            className={`px-3 py-1 text-xs rounded-full capitalize transition-colors ${filter === f
                                    ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
                                    : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
                                }`}
                        >
                            {f}
                        </button>
                    ))}
                </div>
            </div>

            <div className="divide-y divide-gray-200 dark:divide-gray-700">
                {messages.map((msg) => {
                    const Icon = getChannelIcon(msg.channel);

                    return (
                        <div key={msg.id} className="p-4 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                            <div className="flex items-start gap-4">
                                <div className="w-10 h-10 rounded-lg bg-gray-100 dark:bg-gray-700 flex items-center justify-center">
                                    <Icon className="w-5 h-5 text-gray-600 dark:text-gray-400" />
                                </div>

                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 mb-1">
                                        <span className="font-medium text-gray-900 dark:text-white">
                                            {msg.sender}
                                        </span>
                                        <span className="text-xs text-gray-500 dark:text-gray-400">
                                            via {msg.channelName}
                                        </span>
                                        <span className={`text-xs px-2 py-0.5 rounded-full ${getStatusColor(msg.status)}`}>
                                            {msg.status}
                                        </span>
                                    </div>

                                    <p className="text-sm text-gray-600 dark:text-gray-300 mb-2">
                                        {msg.content}
                                    </p>

                                    <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
                                        <span>{format(msg.timestamp, 'h:mm a')}</span>
                                        {msg.assignedAgent && (
                                            <span className="flex items-center gap-1">
                                                <User className="w-3 h-3" />
                                                Assigned to Agent {msg.assignedAgent}
                                            </span>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}