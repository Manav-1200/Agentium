import { useState, useEffect, useRef } from 'react';
import { useWebSocketStore } from '@/store/websocketStore';
import { inboxApi, UnifiedConversation, UnifiedMessage } from '@/services/inboxApi';
import { format } from 'date-fns';
import {
    MessageCircle,
    Smartphone,
    Slack,
    Mail,
    Send,
    Loader2,
    CheckCircle,
    Bot
} from 'lucide-react';
import toast from 'react-hot-toast';

export function InboxPage() {
    const [conversations, setConversations] = useState<UnifiedConversation[]>([]);
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [replyContent, setReplyContent] = useState('');
    const [isSending, setIsSending] = useState(false);

    // Subscribe to websocket events
    const { lastMessage } = useWebSocketStore();

    const messagesEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        loadConversations();
    }, []);

    useEffect(() => {
        if (lastMessage?.type === 'message_created') {
            const msg = lastMessage.message as UnifiedMessage;

            // Re-fetch conversations if a new message arrives 
            // Alternatively, we could update state directly but re-fetching is safer for now
            loadConversations();
        }
    }, [lastMessage]);

    useEffect(() => {
        if (selectedId) {
            scrollToBottom();
        }
    }, [selectedId, conversations]);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    const loadConversations = async () => {
        try {
            const res = await inboxApi.getConversations();
            setConversations(res.conversations);
        } catch (err: any) {
            toast.error(err.message || 'Failed to load conversations');
        } finally {
            setIsLoading(false);
        }
    };

    const handleSendReply = async () => {
        if (!selectedId || !replyContent.trim()) return;

        setIsSending(true);
        try {
            await inboxApi.reply(selectedId, replyContent.trim());
            setReplyContent('');
            await loadConversations();
            toast.success('Reply sent');
        } catch (err: any) {
            toast.error(err.response?.data?.detail || err.message || 'Failed to send reply');
        } finally {
            setIsSending(false);
        }
    };

    const getChannelIcon = (channel?: string) => {
        switch (channel) {
            case 'whatsapp': return <Smartphone className="w-4 h-4" />;
            case 'slack': return <Slack className="w-4 h-4" />;
            case 'email': return <Mail className="w-4 h-4" />;
            case 'telegram': return <MessageCircle className="w-4 h-4" />;
            default: return <MessageCircle className="w-4 h-4" />;
        }
    };

    if (isLoading) {
        return (
            <div className="flex items-center justify-center h-full min-h-[400px]">
                <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
            </div>
        );
    }

    const selectedConv = conversations.find(c => c.id === selectedId);

    return (
        <div className="h-full flex flex-col bg-gray-50 dark:bg-[#0f1117] transition-colors duration-200">
            {/* Header */}
            <div className="flex-shrink-0 bg-white dark:bg-[#161b27] border-b border-gray-200 dark:border-[#1e2535] px-6 py-4">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-blue-100 dark:bg-blue-500/10 flex items-center justify-center text-blue-600 dark:text-blue-400">
                        <MessageCircle className="w-5 h-5" />
                    </div>
                    <div>
                        <h1 className="text-xl font-bold text-gray-900 dark:text-white">Unified Inbox</h1>
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                            Manage conversations across all connected channels
                        </p>
                    </div>
                </div>
            </div>

            <div className="flex-1 flex overflow-hidden max-w-7xl mx-auto w-full">
                {/* Conversation List Sidebar */}
                <div className="w-1/3 bg-white dark:bg-[#161b27] border-r border-gray-200 dark:border-[#1e2535] flex flex-col">
                    <div className="p-4 border-b border-gray-200 dark:border-[#1e2535]">
                        <h2 className="font-semibold text-gray-700 dark:text-gray-300">Active Conversations</h2>
                    </div>
                    <div className="flex-1 overflow-y-auto">
                        {conversations.length === 0 ? (
                            <div className="p-8 text-center text-gray-500 dark:text-gray-400">
                                No active conversations
                            </div>
                        ) : (
                            <div className="divide-y divide-gray-100 dark:divide-[#1e2535]">
                                {conversations.map(conv => {
                                    // Get the most recent message to display preview
                                    const latestMsg = conv.messages && conv.messages.length > 0
                                        ? conv.messages[conv.messages.length - 1]
                                        : null;

                                    // Find channel type from the messages
                                    const externalMsg = conv.messages?.find(m => m.sender_channel);
                                    const channelType = externalMsg?.sender_channel;

                                    return (
                                        <button
                                            key={conv.id}
                                            onClick={() => setSelectedId(conv.id)}
                                            className={`w-full p-4 text-left transition-colors flex items-start gap-4 ${selectedId === conv.id
                                                    ? 'bg-blue-50 dark:bg-blue-500/5'
                                                    : 'hover:bg-gray-50 dark:hover:bg-[#1e2535]/50'
                                                }`}
                                        >
                                            <div className="w-10 h-10 rounded-full bg-gray-100 dark:bg-[#1e2535] flex items-center justify-center text-gray-500 dark:text-gray-400 flex-shrink-0">
                                                {getChannelIcon(channelType)}
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center justify-between mb-1">
                                                    <span className="font-medium text-gray-900 dark:text-gray-100 truncate">
                                                        {conv.title || 'Unknown Sender'}
                                                    </span>
                                                    {conv.last_message_at && (
                                                        <span className="text-xs text-gray-400 dark:text-gray-500 whitespace-nowrap ml-2">
                                                            {format(new Date(conv.last_message_at), 'h:mm a')}
                                                        </span>
                                                    )}
                                                </div>
                                                <p className="text-sm text-gray-500 dark:text-gray-400 truncate">
                                                    {latestMsg ? latestMsg.content : 'No messages'}
                                                </p>
                                            </div>
                                        </button>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                </div>

                {/* Main Chat Area */}
                <div className="w-2/3 flex flex-col bg-gray-50 dark:bg-[#0f1117]">
                    {!selectedConv ? (
                        <div className="flex-1 flex items-center justify-center text-gray-500 dark:text-gray-400">
                            Select a conversation to view messages
                        </div>
                    ) : (
                        <>
                            {/* Chat Header */}
                            <div className="p-4 bg-white dark:bg-[#161b27] border-b border-gray-200 dark:border-[#1e2535] flex items-center justify-between">
                                <h3 className="font-semibold text-gray-900 dark:text-white">
                                    {selectedConv.title}
                                </h3>
                                <span className={`text-xs px-2 py-1 rounded-full border ${selectedConv.is_active
                                        ? 'bg-green-50 text-green-700 border-green-200 dark:bg-green-500/10 dark:text-green-400 dark:border-green-500/20'
                                        : 'bg-gray-50 text-gray-700 border-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:border-gray-700'
                                    }`}>
                                    {selectedConv.is_active ? 'Active' : 'Archived'}
                                </span>
                            </div>

                            {/* Chat Messages */}
                            <div className="flex-1 overflow-y-auto p-6 space-y-4">
                                {selectedConv.messages?.map(msg => {
                                    const isAdmin = msg.role === 'system' || msg.metadata?.sent_by_admin;
                                    const isBot = msg.role === 'head_of_council'; // AI responses
                                    const isUser = !isAdmin && !isBot;

                                    return (
                                        <div key={msg.id} className={`flex max-w-[80%] ${isAdmin ? 'ml-auto' : ''}`}>
                                            <div className={`p-4 rounded-2xl ${isAdmin
                                                    ? 'bg-blue-600 text-white rounded-tr-none'
                                                    : isBot
                                                        ? 'bg-purple-50 dark:bg-purple-900/20 border border-purple-100 dark:border-purple-800 text-gray-800 dark:text-gray-200 rounded-tl-none'
                                                        : 'bg-white dark:bg-[#161b27] border border-gray-200 dark:border-[#1e2535] text-gray-900 dark:text-gray-100 rounded-tl-none'
                                                }`}>
                                                {(isUser || isBot) && (
                                                    <div className="flex items-center gap-2 mb-2">
                                                        {isBot ? (
                                                            <>
                                                                <Bot className="w-4 h-4 text-purple-500" />
                                                                <span className="text-xs font-semibold text-purple-700 dark:text-purple-400">AI Assistant</span>
                                                            </>
                                                        ) : (
                                                            <>
                                                                <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 flex items-center gap-1">
                                                                    {getChannelIcon(msg.sender_channel)}
                                                                    {msg.sender_channel || 'Unknown Channel'}
                                                                </span>
                                                            </>
                                                        )}
                                                    </div>
                                                )}

                                                <div className="whitespace-pre-wrap text-sm">
                                                    {msg.content}
                                                </div>

                                                <div className={`text-[10px] mt-2 text-right ${isAdmin ? 'text-blue-200' : 'text-gray-400 dark:text-gray-500'
                                                    }`}>
                                                    {format(new Date(msg.created_at), 'h:mm a')}
                                                    {isAdmin && msg.metadata?.channel_routed && (
                                                        <span className="ml-1 opacity-70">
                                                            (Sent via {msg.metadata.channel_routed})
                                                        </span>
                                                    )}
                                                </div>
                                            </div>
                                        </div>
                                    );
                                })}
                                <div ref={messagesEndRef} />
                            </div>

                            {/* Reply Input */}
                            <div className="p-4 bg-white dark:bg-[#161b27] border-t border-gray-200 dark:border-[#1e2535]">
                                <div className="flex items-end gap-2">
                                    <textarea
                                        value={replyContent}
                                        onChange={e => setReplyContent(e.target.value)}
                                        onKeyDown={e => {
                                            if (e.key === 'Enter' && !e.shiftKey) {
                                                e.preventDefault();
                                                handleSendReply();
                                            }
                                        }}
                                        placeholder="Type a reply..."
                                        className="flex-1 max-h-32 min-h-[44px] p-3 bg-gray-50 dark:bg-[#0f1117] border border-gray-200 dark:border-[#1e2535] rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:text-white resize-none"
                                        rows={1}
                                    />
                                    <button
                                        onClick={handleSendReply}
                                        disabled={!replyContent.trim() || isSending}
                                        className="p-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl disabled:opacity-50 transition-colors"
                                    >
                                        {isSending ? (
                                            <Loader2 className="w-5 h-5 animate-spin" />
                                        ) : (
                                            <Send className="w-5 h-5" />
                                        )}
                                    </button>
                                </div>
                                <p className="text-xs text-gray-400 mt-2">
                                    Your reply will be routed back to the user's original channel.
                                </p>
                            </div>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}
