import { useState, useRef, useEffect } from 'react';
import { useChatStore } from '@/store/chatStore';
import { useAuthStore } from '@/store/authStore';
import {
    Send,
    Crown,
    Bot,
    User,
    Trash2,
    History,
    Sparkles,
    AlertCircle,
    Loader2,
    CheckCircle
} from 'lucide-react';
import { format } from 'date-fns';
import toast from 'react-hot-toast';

export function ChatPage() {
    const [input, setInput] = useState('');
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);
    const { user } = useAuthStore();
    const { messages, isLoading, currentStreamingMessage, sendMessage, clearHistory } = useChatStore();

    // Scroll to bottom on new messages or streaming updates
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, currentStreamingMessage]);

    // Auto-resize textarea
    useEffect(() => {
        if (inputRef.current) {
            inputRef.current.style.height = 'auto';
            inputRef.current.style.height = inputRef.current.scrollHeight + 'px';
        }
    }, [input]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim() || isLoading) return;

        const content = input.trim();
        setInput('');
        if (inputRef.current) {
            inputRef.current.style.height = 'auto';
        }

        await sendMessage(content);
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit(e);
        }
    };

    const handleClear = () => {
        if (confirm('Clear all conversation history?')) {
            clearHistory();
            toast.success('History cleared');
        }
    };

    const getMessageIcon = (role: string) => {
        switch (role) {
            case 'sovereign':
                return <Crown className="w-5 h-5 text-yellow-600" />;
            case 'head_of_council':
                return <Bot className="w-5 h-5 text-blue-600" />;
            default:
                return <AlertCircle className="w-5 h-5 text-red-600" />;
        }
    };

    const getMessageStyle = (role: string) => {
        switch (role) {
            case 'sovereign':
                return 'bg-blue-600 text-white ml-12';
            case 'head_of_council':
                return 'bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 mr-12';
            default:
                return 'bg-red-50 dark:bg-red-900/20 text-red-900 dark:text-red-300 mx-12';
        }
    };

    return (
        <div className="h-[calc(100vh-4rem)] flex flex-col max-w-5xl mx-auto">
            {/* Header */}
            <div className="flex items-center justify-between mb-6 pb-4 border-b border-gray-200 dark:border-gray-700">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white">
                        <Crown className="w-6 h-6" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
                            Command Interface
                            <span className="text-xs px-2 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded-full font-medium">
                                00001
                            </span>
                        </h1>
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                            Direct channel to the Head of Council
                        </p>
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    <button
                        onClick={handleClear}
                        className="flex items-center gap-2 px-3 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
                        title="Clear History"
                    >
                        <Trash2 className="w-4 h-4" />
                        <span className="hidden sm:inline">Clear</span>
                    </button>
                </div>
            </div>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto space-y-6 mb-6 pr-2">
                {messages.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-center p-8">
                        <div className="w-20 h-20 rounded-full bg-gradient-to-br from-blue-100 to-purple-100 dark:from-blue-900/30 dark:to-purple-900/30 flex items-center justify-center mb-4">
                            <Sparkles className="w-10 h-10 text-blue-600 dark:text-blue-400" />
                        </div>
                        <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
                            Welcome, Sovereign
                        </h3>
                        <p className="text-gray-600 dark:text-gray-400 max-w-md mb-6">
                            Issue your commands to the Head of Council. Your directives will be deliberated
                            upon by the Council, coordinated by Lead Agents, and executed by Task Agents.
                        </p>

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-lg">
                            {[
                                "Analyze recent system performance",
                                "Spawn a new research task agent",
                                "Review constitutional amendments",
                                "Execute code analysis task"
                            ].map((suggestion) => (
                                <button
                                    key={suggestion}
                                    onClick={() => setInput(suggestion)}
                                    className="p-3 text-left text-sm text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-800/50 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 transition-colors"
                                >
                                    {suggestion}
                                </button>
                            ))}
                        </div>
                    </div>
                ) : (
                    messages.map((message) => (
                        <div
                            key={message.id}
                            className={`flex gap-4 ${message.role === 'sovereign' ? 'flex-row-reverse' : ''}`}
                        >
                            {/* Avatar */}
                            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
                                {getMessageIcon(message.role)}
                            </div>

                            {/* Message Bubble */}
                            <div className={`flex-1 max-w-3xl ${message.role === 'sovereign' ? 'text-right' : ''}`}>
                                <div className="flex items-center gap-2 mb-1">
                                    <span className="text-sm font-medium text-gray-900 dark:text-white">
                                        {message.role === 'sovereign'
                                            ? user?.username
                                            : 'Head of Council (00001)'}
                                    </span>
                                    <span className="text-xs text-gray-500 dark:text-gray-400">
                                        {format(message.timestamp, 'h:mm a')}
                                    </span>
                                    {message.status === 'error' && (
                                        <span className="text-xs text-red-600 flex items-center gap-1">
                                            <AlertCircle className="w-3 h-3" />
                                            Failed
                                        </span>
                                    )}
                                    {message.metadata?.task_created && (
                                        <span className="text-xs text-green-600 flex items-center gap-1 bg-green-50 dark:bg-green-900/30 px-2 py-0.5 rounded-full">
                                            <CheckCircle className="w-3 h-3" />
                                            Task {message.metadata.task_id} Created
                                        </span>
                                    )}
                                </div>

                                <div className={`inline-block text-left px-4 py-3 rounded-2xl shadow-sm ${getMessageStyle(message.role)}`}>
                                    <div className="whitespace-pre-wrap text-sm leading-relaxed">
                                        {message.content}
                                    </div>

                                    {message.metadata && (
                                        <div className="mt-2 pt-2 border-t border-white/20 text-xs opacity-70 flex flex-wrap gap-2">
                                            <span>Agent: {message.metadata.agent_used}</span>
                                            <span>•</span>
                                            <span>Model: {message.metadata.model}</span>
                                            {message.metadata.latency_ms && (
                                                <>
                                                    <span>•</span>
                                                    <span>{message.metadata.latency_ms}ms</span>
                                                </>
                                            )}
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    ))
                )}

                {/* Streaming Message (Real-time response) */}
                {isLoading && currentStreamingMessage && (
                    <div className="flex gap-4">
                        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
                            <Bot className="w-5 h-5 text-blue-600 animate-pulse" />
                        </div>
                        <div className="flex-1 max-w-3xl">
                            <div className="flex items-center gap-2 mb-1">
                                <span className="text-sm font-medium text-gray-900 dark:text-white">
                                    Head of Council (00001)
                                </span>
                                <span className="text-xs text-gray-500 dark:text-gray-400">
                                    {format(new Date(), 'h:mm a')}
                                </span>
                                <span className="flex items-center gap-1 text-xs text-blue-600 animate-pulse">
                                    <div className="w-1.5 h-1.5 bg-blue-600 rounded-full animate-bounce" />
                                    Thinking...
                                </span>
                            </div>
                            <div className="inline-block text-left px-4 py-3 rounded-2xl shadow-sm bg-white dark:bg-gray-800 border border-blue-200 dark:border-blue-800 mr-12">
                                <div className="whitespace-pre-wrap text-sm leading-relaxed text-gray-900 dark:text-white">
                                    {currentStreamingMessage}
                                    <span className="inline-block w-0.5 h-4 bg-blue-600 animate-pulse ml-0.5 align-text-bottom" />
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* Initial loading state (before first chunk arrives) */}
                {isLoading && !currentStreamingMessage && (
                    <div className="flex gap-4">
                        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
                            <Bot className="w-5 h-5 text-blue-600 animate-pulse" />
                        </div>
                        <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-800/50 px-4 py-2 rounded-full">
                            <Loader2 className="w-4 h-4 animate-spin" />
                            <span className="text-sm">Head of Council is deliberating...</span>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
                <form onSubmit={handleSubmit} className="relative">
                    <div className="flex gap-2 items-end bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl p-2 shadow-lg">
                        <textarea
                            ref={inputRef}
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={handleKeyDown}
                            placeholder="Issue your command to the Head of Council..."
                            className="flex-1 max-h-32 px-4 py-3 bg-transparent border-0 focus:ring-0 resize-none text-gray-900 dark:text-white placeholder-gray-400 text-sm disabled:opacity-50"
                            rows={1}
                            disabled={isLoading}
                        />

                        <button
                            type="submit"
                            disabled={!input.trim() || isLoading}
                            className="flex-shrink-0 p-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl transition-colors"
                        >
                            {isLoading ? (
                                <Loader2 className="w-5 h-5 animate-spin" />
                            ) : (
                                <Send className="w-5 h-5" />
                            )}
                        </button>
                    </div>

                    <p className="text-xs text-center text-gray-500 dark:text-gray-400 mt-2">
                        {isLoading ? 'Receiving response...' : 'Press Enter to send, Shift + Enter for new line'}
                    </p>
                </form>
            </div>

            {/* Status Bar */}
            <div className="mt-4 flex items-center justify-center gap-4 text-xs text-gray-500 dark:text-gray-400">
                <div className="flex items-center gap-1">
                    <div className="w-2 h-2 rounded-full bg-green-500" />
                    Head of Council Online
                </div>
                <div className="flex items-center gap-1">
                    <History className="w-3 h-3" />
                    Constitution v1.0.0 Active
                </div>
                <div className="flex items-center gap-1">
                    <User className="w-3 h-3" />
                    {messages.filter(m => m.role === 'sovereign').length} Commands Issued
                </div>
            </div>
        </div>
    );
}