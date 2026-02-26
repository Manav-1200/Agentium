// src/pages/ChannelsPage.tsx
import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, Channel, ChannelTypeSlug, ChannelStatus } from '@/services/api';
import toast from 'react-hot-toast';
import {
    Radio,
    Plus,
    RefreshCw,
    Loader2,
    CheckCircle2,
    XCircle,
    Clock,
    AlertTriangle,
    Trash2,
    Settings,
    Send,
    Activity,
    Inbox,
    ChevronDown,
    ChevronUp,
    Zap,
    RotateCcw,
    ExternalLink,
    Wifi,
    WifiOff,
    MessageSquare,
    ArrowUpRight,
} from 'lucide-react';

// ─── Channel type config ──────────────────────────────────────────────────────

const CHANNEL_ICONS: Record<string, string> = {
    whatsapp: '💬',
    slack: '🔷',
    telegram: '✈️',
    email: '✉️',
    discord: '🎮',
    signal: '🔒',
    google_chat: '💠',
    teams: '🟦',
    zalo: '🟩',
    matrix: '🔳',
    imessage: '🍎',
    custom: '🔗',
};

const STATUS_CONFIG: Record<ChannelStatus, { label: string; color: string; bg: string; border: string; dot: string }> = {
    active:       { label: 'Active',       color: 'text-emerald-400', bg: 'bg-emerald-400/10', border: 'border-emerald-400/20', dot: 'bg-emerald-400' },
    pending:      { label: 'Pending',      color: 'text-yellow-400',  bg: 'bg-yellow-400/10',  border: 'border-yellow-400/20',  dot: 'bg-yellow-400' },
    error:        { label: 'Error',        color: 'text-red-400',     bg: 'bg-red-400/10',     border: 'border-red-400/20',     dot: 'bg-red-400' },
    disconnected: { label: 'Disconnected', color: 'text-gray-400',    bg: 'bg-gray-400/10',    border: 'border-gray-400/20',    dot: 'bg-gray-400' },
};

const CHANNEL_TYPE_OPTIONS: ChannelTypeSlug[] = [
    'whatsapp', 'slack', 'telegram', 'email', 'discord',
    'signal', 'google_chat', 'teams', 'zalo', 'matrix', 'imessage', 'custom',
];

// ─── Create channel modal ─────────────────────────────────────────────────────

interface CreateModalProps {
    onClose: () => void;
    onCreated: () => void;
}

function CreateChannelModal({ onClose, onCreated }: CreateModalProps) {
    const [name, setName] = useState('');
    const [type, setType] = useState<ChannelTypeSlug>('whatsapp');
    const [autoCreateTasks, setAutoCreateTasks] = useState(true);
    const [requireApproval, setRequireApproval] = useState(false);
    const [configText, setConfigText] = useState('{}');
    const [saving, setSaving] = useState(false);
    const [configError, setConfigError] = useState('');

    const handleSubmit = async () => {
        // Validate JSON config
        let config: Record<string, unknown> = {};
        try {
            config = JSON.parse(configText);
            setConfigError('');
        } catch {
            setConfigError('Invalid JSON configuration');
            return;
        }

        if (!name.trim()) {
            toast.error('Channel name is required');
            return;
        }

        setSaving(true);
        try {
            await api.post('/channels/', {
                name: name.trim(),
                type,
                config,
                auto_create_tasks: autoCreateTasks,
                require_approval: requireApproval,
            });
            toast.success('Channel created successfully');
            onCreated();
            onClose();
        } catch (err: any) {
            toast.error(err?.response?.data?.detail ?? 'Failed to create channel');
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-gray-800 border border-gray-600/50 rounded-2xl w-full max-w-lg shadow-2xl">
                <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700/50">
                    <h2 className="text-lg font-semibold text-white">Add Channel</h2>
                    <button
                        onClick={onClose}
                        className="text-gray-400 hover:text-white transition-colors p-1"
                    >
                        <XCircle className="w-5 h-5" />
                    </button>
                </div>

                <div className="px-6 py-4 space-y-4">
                    {/* Name */}
                    <div>
                        <label className="text-xs text-gray-400 font-medium block mb-1">Channel Name *</label>
                        <input
                            type="text"
                            value={name}
                            onChange={e => setName(e.target.value)}
                            placeholder="e.g. WhatsApp Business"
                            className="w-full bg-gray-700 border border-gray-600/50 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                        />
                    </div>

                    {/* Type */}
                    <div>
                        <label className="text-xs text-gray-400 font-medium block mb-1">Channel Type *</label>
                        <select
                            value={type}
                            onChange={e => setType(e.target.value as ChannelTypeSlug)}
                            className="w-full bg-gray-700 border border-gray-600/50 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
                        >
                            {CHANNEL_TYPE_OPTIONS.map(t => (
                                <option key={t} value={t}>
                                    {CHANNEL_ICONS[t]} {t.replace('_', ' ')}
                                </option>
                            ))}
                        </select>
                    </div>

                    {/* Config */}
                    <div>
                        <label className="text-xs text-gray-400 font-medium block mb-1">Configuration (JSON)</label>
                        <textarea
                            value={configText}
                            onChange={e => { setConfigText(e.target.value); setConfigError(''); }}
                            rows={4}
                            placeholder='{ "bot_token": "...", "phone_number_id": "..." }'
                            className={`w-full bg-gray-700 border rounded-lg px-3 py-2 text-sm text-gray-200 font-mono placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none ${
                                configError ? 'border-red-500/60' : 'border-gray-600/50'
                            }`}
                        />
                        {configError && (
                            <p className="text-xs text-red-400 mt-1">{configError}</p>
                        )}
                    </div>

                    {/* Options */}
                    <div className="flex gap-4">
                        <label className="flex items-center gap-2 cursor-pointer">
                            <input
                                type="checkbox"
                                checked={autoCreateTasks}
                                onChange={e => setAutoCreateTasks(e.target.checked)}
                                className="rounded accent-blue-500"
                            />
                            <span className="text-sm text-gray-300">Auto-create tasks</span>
                        </label>
                        <label className="flex items-center gap-2 cursor-pointer">
                            <input
                                type="checkbox"
                                checked={requireApproval}
                                onChange={e => setRequireApproval(e.target.checked)}
                                className="rounded accent-blue-500"
                            />
                            <span className="text-sm text-gray-300">Require approval</span>
                        </label>
                    </div>
                </div>

                <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-700/50">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 rounded-lg text-sm text-gray-400 hover:text-gray-200 transition-colors"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleSubmit}
                        disabled={saving}
                        className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-colors disabled:opacity-50"
                    >
                        {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                        Create Channel
                    </button>
                </div>
            </div>
        </div>
    );
}

// ─── Test message modal ───────────────────────────────────────────────────────

interface TestModalProps {
    channel: Channel;
    onClose: () => void;
}

function TestMessageModal({ channel, onClose }: TestModalProps) {
    const [recipient, setRecipient] = useState('');
    const [content, setContent] = useState('Hello from Agentium! 👋');
    const [sending, setSending] = useState(false);

    const handleSend = async () => {
        if (!recipient.trim()) { toast.error('Recipient required'); return; }
        setSending(true);
        try {
            await api.post(`/channels/${channel.id}/send`, { recipient, content });
            toast.success('Test message sent!');
            onClose();
        } catch (err: any) {
            toast.error(err?.response?.data?.detail ?? 'Send failed');
        } finally {
            setSending(false);
        }
    };

    return (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-gray-800 border border-gray-600/50 rounded-2xl w-full max-w-md shadow-2xl">
                <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700/50">
                    <h2 className="text-base font-semibold text-white">
                        Send Test Message — {CHANNEL_ICONS[channel.type]} {channel.name}
                    </h2>
                    <button onClick={onClose} className="text-gray-400 hover:text-white p-1">
                        <XCircle className="w-5 h-5" />
                    </button>
                </div>
                <div className="px-6 py-4 space-y-3">
                    <div>
                        <label className="text-xs text-gray-400 font-medium block mb-1">Recipient</label>
                        <input
                            type="text"
                            value={recipient}
                            onChange={e => setRecipient(e.target.value)}
                            placeholder="Phone number, chat ID, email…"
                            className="w-full bg-gray-700 border border-gray-600/50 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                        />
                    </div>
                    <div>
                        <label className="text-xs text-gray-400 font-medium block mb-1">Message</label>
                        <textarea
                            value={content}
                            onChange={e => setContent(e.target.value)}
                            rows={3}
                            className="w-full bg-gray-700 border border-gray-600/50 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none"
                        />
                    </div>
                </div>
                <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-700/50">
                    <button onClick={onClose} className="px-4 py-2 rounded-lg text-sm text-gray-400 hover:text-gray-200 transition-colors">
                        Cancel
                    </button>
                    <button
                        onClick={handleSend}
                        disabled={sending}
                        className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-colors disabled:opacity-50"
                    >
                        {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                        Send
                    </button>
                </div>
            </div>
        </div>
    );
}

// ─── Channel Card ─────────────────────────────────────────────────────────────

interface ChannelCardProps {
    channel: Channel;
    onRefresh: () => void;
    onDelete: (id: string) => void;
    onTest: (channel: Channel) => void;
    onViewLog: (id: string) => void;
}

function ChannelCard({ channel, onRefresh, onDelete, onTest, onViewLog }: ChannelCardProps) {
    const [expanded, setExpanded] = useState(false);
    const [testing, setTesting] = useState(false);
    const [resetting, setResetting] = useState(false);
    const [deleting, setDeleting] = useState(false);

    const st = STATUS_CONFIG[channel.status] ?? STATUS_CONFIG.pending;

    const handleTest = async () => {
        setTesting(true);
        try {
            await api.post(`/channels/${channel.id}/test`);
            toast.success('Connection test passed');
            onRefresh();
        } catch (err: any) {
            toast.error(err?.response?.data?.detail ?? 'Test failed');
        } finally {
            setTesting(false);
        }
    };

    const handleReset = async () => {
        setResetting(true);
        try {
            await api.post(`/channels/${channel.id}/reset`);
            toast.success('Channel reset');
            onRefresh();
        } catch (err: any) {
            toast.error(err?.response?.data?.detail ?? 'Reset failed');
        } finally {
            setResetting(false);
        }
    };

    const handleDelete = async () => {
        if (!window.confirm(`Delete channel "${channel.name}"? This cannot be undone.`)) return;
        setDeleting(true);
        try {
            await api.delete(`/channels/${channel.id}`);
            toast.success('Channel deleted');
            onDelete(channel.id);
        } catch (err: any) {
            toast.error(err?.response?.data?.detail ?? 'Delete failed');
        } finally {
            setDeleting(false);
        }
    };

    return (
        <div className={`rounded-xl border bg-gray-800/50 overflow-hidden transition-colors hover:bg-gray-800/80 ${
            channel.status === 'error' ? 'border-red-500/25' : 'border-gray-700/50'
        }`}>
            {/* Header row */}
            <div
                className="flex items-center gap-3 px-4 py-3 cursor-pointer"
                onClick={() => setExpanded(e => !e)}
            >
                {/* Icon */}
                <span className="text-2xl w-9 text-center flex-shrink-0">
                    {CHANNEL_ICONS[channel.type] ?? '📡'}
                </span>

                {/* Name & status */}
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-semibold text-gray-100">{channel.name}</span>
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${st.color} ${st.bg} border ${st.border}`}>
                            <span className={`w-1.5 h-1.5 rounded-full ${st.dot} ${channel.status === 'active' ? 'animate-pulse' : ''}`} />
                            {st.label}
                        </span>
                    </div>
                    <div className="flex items-center gap-3 mt-0.5 text-xs text-gray-500">
                        <span className="capitalize">{channel.type.replace('_', ' ')}</span>
                        {channel.config.phone_number && <span>{channel.config.phone_number}</span>}
                        {channel.config.webhook_url && (
                            <span className="flex items-center gap-1">
                                <Wifi className="w-3 h-3" /> Webhook configured
                            </span>
                        )}
                    </div>
                </div>

                {/* Stats */}
                <div className="hidden sm:flex items-center gap-4 text-xs text-gray-500 flex-shrink-0">
                    <div className="text-center">
                        <div className="text-gray-300 font-medium">{channel.stats.received.toLocaleString()}</div>
                        <div>received</div>
                    </div>
                    <div className="text-center">
                        <div className="text-gray-300 font-medium">{channel.stats.sent.toLocaleString()}</div>
                        <div>sent</div>
                    </div>
                </div>

                {/* Expand chevron */}
                {expanded
                    ? <ChevronUp className="w-4 h-4 text-gray-500 flex-shrink-0" />
                    : <ChevronDown className="w-4 h-4 text-gray-500 flex-shrink-0" />
                }
            </div>

            {/* Expanded actions & details */}
            {expanded && (
                <div className="border-t border-gray-700/50 px-4 py-3 bg-gray-900/30 space-y-3">
                    {/* Routing info */}
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                        <div>
                            <span className="text-xs text-gray-500 block mb-0.5">Default Agent</span>
                            <span className="text-xs text-gray-300 font-mono">
                                {channel.routing.default_agent ?? 'Head of Council'}
                            </span>
                        </div>
                        <div>
                            <span className="text-xs text-gray-500 block mb-0.5">Auto Tasks</span>
                            <span className={`text-xs font-medium ${channel.routing.auto_create_tasks ? 'text-emerald-400' : 'text-gray-400'}`}>
                                {channel.routing.auto_create_tasks ? 'Enabled' : 'Disabled'}
                            </span>
                        </div>
                        <div>
                            <span className="text-xs text-gray-500 block mb-0.5">Approval</span>
                            <span className={`text-xs font-medium ${channel.routing.require_approval ? 'text-amber-400' : 'text-gray-400'}`}>
                                {channel.routing.require_approval ? 'Required' : 'Not required'}
                            </span>
                        </div>
                        {channel.stats.last_message && (
                            <div className="col-span-full">
                                <span className="text-xs text-gray-500 block mb-0.5">Last Message</span>
                                <span className="text-xs text-gray-300">
                                    {new Date(channel.stats.last_message).toLocaleString()}
                                </span>
                            </div>
                        )}
                    </div>

                    {/* Action buttons */}
                    <div className="flex flex-wrap gap-2">
                        {/* View Message Log — primary CTA */}
                        <button
                            onClick={() => onViewLog(channel.id)}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600/20 border border-blue-500/30 text-blue-300 text-xs font-medium hover:bg-blue-600/30 transition-colors"
                        >
                            <Inbox className="w-3.5 h-3.5" />
                            Message Log
                            <ArrowUpRight className="w-3 h-3 opacity-60" />
                        </button>

                        {/* Test connection */}
                        <button
                            onClick={handleTest}
                            disabled={testing}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-700 border border-gray-600/50 text-gray-300 text-xs font-medium hover:bg-gray-600 transition-colors disabled:opacity-50"
                        >
                            {testing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Activity className="w-3.5 h-3.5" />}
                            Test
                        </button>

                        {/* Send test message */}
                        <button
                            onClick={() => onTest(channel)}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-700 border border-gray-600/50 text-gray-300 text-xs font-medium hover:bg-gray-600 transition-colors"
                        >
                            <MessageSquare className="w-3.5 h-3.5" />
                            Send Test
                        </button>

                        {/* Reset circuit breaker */}
                        {channel.status === 'error' && (
                            <button
                                onClick={handleReset}
                                disabled={resetting}
                                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500/15 border border-amber-500/30 text-amber-400 text-xs font-medium hover:bg-amber-500/25 transition-colors disabled:opacity-50"
                            >
                                {resetting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RotateCcw className="w-3.5 h-3.5" />}
                                Reset
                            </button>
                        )}

                        {/* Delete */}
                        <button
                            onClick={handleDelete}
                            disabled={deleting}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-medium hover:bg-red-500/20 transition-colors disabled:opacity-50 ml-auto"
                        >
                            {deleting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                            Delete
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export function ChannelsPage() {
    const navigate = useNavigate();
    const [channels, setChannels] = useState<Channel[]>([]);
    const [loading, setLoading] = useState(true);
    const [showCreate, setShowCreate] = useState(false);
    const [testChannel, setTestChannel] = useState<Channel | null>(null);
    const [statusFilter, setStatusFilter] = useState<ChannelStatus | 'all'>('all');
    const [typeFilter, setTypeFilter] = useState<ChannelTypeSlug | 'all'>('all');
    const [stats, setStats] = useState<Record<string, number>>({});

    const fetchChannels = useCallback(async () => {
        setLoading(true);
        try {
            const params: Record<string, string> = {};
            if (statusFilter !== 'all') params.status = statusFilter;
            if (typeFilter !== 'all') params.channel_type = typeFilter;

            const { data } = await api.get('/channels/', { params });
            setChannels(data.channels ?? []);
            setStats(data.by_status ?? {});
        } catch {
            toast.error('Failed to load channels');
        } finally {
            setLoading(false);
        }
    }, [statusFilter, typeFilter]);

    useEffect(() => { fetchChannels(); }, [fetchChannels]);

    const handleViewLog = (channelId: string) => {
        navigate(`/message-log?channel_id=${channelId}`);
    };

    const handleDelete = (id: string) => {
        setChannels(prev => prev.filter(c => c.id !== id));
    };

    const totalReceived = channels.reduce((s, c) => s + c.stats.received, 0);
    const totalSent = channels.reduce((s, c) => s + c.stats.sent, 0);
    const activeCount = stats['active'] ?? 0;
    const errorCount = stats['error'] ?? 0;

    return (
        <div className="flex flex-col h-full min-h-0 bg-gray-900 text-gray-100">
            {/* Header */}
            <div className="flex-shrink-0 px-6 py-4 border-b border-gray-700/50 bg-gray-900/80 backdrop-blur-sm">
                <div className="flex items-center justify-between flex-wrap gap-3">
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center">
                            <Radio className="w-4 h-4 text-blue-400" />
                        </div>
                        <div>
                            <h1 className="text-lg font-semibold text-gray-100">Channels</h1>
                            <p className="text-xs text-gray-400">
                                {channels.length} channel{channels.length !== 1 ? 's' : ''} configured
                            </p>
                        </div>
                    </div>

                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => navigate('/message-log')}
                            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-gray-800 border border-gray-600/50 text-gray-300 text-sm hover:bg-gray-700 hover:text-gray-100 transition-colors"
                        >
                            <Inbox className="w-4 h-4" />
                            All Message Logs
                        </button>
                        <button
                            onClick={fetchChannels}
                            className="p-2 rounded-lg bg-gray-800 border border-gray-600/50 text-gray-400 hover:text-gray-200 transition-colors"
                        >
                            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                        </button>
                        <button
                            onClick={() => setShowCreate(true)}
                            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-colors"
                        >
                            <Plus className="w-4 h-4" />
                            Add Channel
                        </button>
                    </div>
                </div>

                {/* Summary stats */}
                <div className="flex gap-4 mt-3 flex-wrap">
                    {[
                        { label: 'Active',    value: activeCount,       color: 'text-emerald-400' },
                        { label: 'Errors',    value: errorCount,        color: errorCount > 0 ? 'text-red-400' : 'text-gray-400' },
                        { label: 'Received',  value: totalReceived,     color: 'text-blue-400' },
                        { label: 'Sent',      value: totalSent,         color: 'text-purple-400' },
                    ].map(s => (
                        <div key={s.label} className="flex items-center gap-1.5">
                            <span className={`text-sm font-semibold ${s.color}`}>{s.value.toLocaleString()}</span>
                            <span className="text-xs text-gray-500">{s.label}</span>
                        </div>
                    ))}
                </div>

                {/* Filters */}
                <div className="flex gap-2 mt-3 flex-wrap">
                    {/* Status filter */}
                    <div className="flex gap-1">
                        {(['all', 'active', 'pending', 'error', 'disconnected'] as const).map(s => (
                            <button
                                key={s}
                                onClick={() => setStatusFilter(s)}
                                className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors border ${
                                    statusFilter === s
                                        ? 'bg-blue-600/30 border-blue-500/50 text-blue-300'
                                        : 'bg-gray-800 border-gray-600/40 text-gray-400 hover:text-gray-200'
                                }`}
                            >
                                {s === 'all' ? 'All' : STATUS_CONFIG[s as ChannelStatus]?.label ?? s}
                                {s !== 'all' && stats[s] !== undefined && (
                                    <span className="ml-1 opacity-60">({stats[s]})</span>
                                )}
                            </button>
                        ))}
                    </div>

                    {/* Type filter */}
                    <select
                        value={typeFilter}
                        onChange={e => setTypeFilter(e.target.value as ChannelTypeSlug | 'all')}
                        className="bg-gray-800 border border-gray-600/40 rounded-lg px-2 py-1 text-xs text-gray-300 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    >
                        <option value="all">All types</option>
                        {CHANNEL_TYPE_OPTIONS.map(t => (
                            <option key={t} value={t}>{CHANNEL_ICONS[t]} {t.replace('_', ' ')}</option>
                        ))}
                    </select>
                </div>
            </div>

            {/* Channel list */}
            <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
                {loading && channels.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-20 text-gray-500">
                        <Loader2 className="w-8 h-8 animate-spin mb-3" />
                        <p className="text-sm">Loading channels…</p>
                    </div>
                ) : channels.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-20 text-gray-500">
                        <WifiOff className="w-10 h-10 mb-3 opacity-30" />
                        <p className="text-sm font-medium">No channels configured</p>
                        <p className="text-xs mt-1 text-gray-600">Add a channel to start routing external messages</p>
                        <button
                            onClick={() => setShowCreate(true)}
                            className="mt-4 flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-colors"
                        >
                            <Plus className="w-4 h-4" />
                            Add your first channel
                        </button>
                    </div>
                ) : (
                    channels.map(channel => (
                        <ChannelCard
                            key={channel.id}
                            channel={channel}
                            onRefresh={fetchChannels}
                            onDelete={handleDelete}
                            onTest={setTestChannel}
                            onViewLog={handleViewLog}
                        />
                    ))
                )}
            </div>

            {/* Modals */}
            {showCreate && (
                <CreateChannelModal
                    onClose={() => setShowCreate(false)}
                    onCreated={fetchChannels}
                />
            )}
            {testChannel && (
                <TestMessageModal
                    channel={testChannel}
                    onClose={() => setTestChannel(null)}
                />
            )}
        </div>
    );
}