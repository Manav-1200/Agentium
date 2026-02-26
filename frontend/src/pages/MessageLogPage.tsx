/**

 * frontend/src/pages/MessageLogPage.tsx
 *
 * Cross-channel message log with:
 *   - Filter by channel, channel type, agent, date range, success/failure
 *   - Full-text search
 *   - Per-message replay for failures
 *   - Bulk replay failed
 *   - Pagination
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Search, Filter, RefreshCw, RotateCcw, ChevronLeft, ChevronRight,
  CheckCircle2, XCircle, Clock, Loader2, AlertTriangle, Inbox,
  MessageSquare, Calendar, User, Hash, LayoutGrid,
  ChevronDown, X, Play, AlertCircle, Zap
} from 'lucide-react';
import { api } from '@/services/api';
import { channelMessagesApi, ChannelMessage, MessageLogFilters } from '@/services/channelMessages';
import toast from 'react-hot-toast';

// ─── Channel icons (emoji fallback) ──────────────────────────────────────────

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

const STATUS_CONFIG = {
  received:   { label: 'Received',   color: 'text-blue-400',   bg: 'bg-blue-400/10',   icon: Clock },
  processing: { label: 'Processing', color: 'text-yellow-400', bg: 'bg-yellow-400/10', icon: Loader2 },
  responded:  { label: 'Responded',  color: 'text-emerald-400', bg: 'bg-emerald-400/10', icon: CheckCircle2 },
  failed:     { label: 'Failed',     color: 'text-red-400',    bg: 'bg-red-400/10',    icon: XCircle },
};

const CHANNEL_TYPE_OPTIONS = [
  'whatsapp','slack','telegram','email','discord',
  'signal','google_chat','teams','zalo','matrix','imessage','custom'
];

// ─── Sub-components ───────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status as keyof typeof STATUS_CONFIG] ?? STATUS_CONFIG.received;
  const Icon = cfg.icon;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${cfg.color} ${cfg.bg}`}>
      <Icon className={`w-3 h-3 ${status === 'processing' ? 'animate-spin' : ''}`} />
      {cfg.label}
    </span>
  );
}

function ChannelBadge({ type, name }: { type: string; name: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-gray-700/50 text-gray-300 text-xs font-medium border border-gray-600/40">
      <span className="text-sm leading-none">{CHANNEL_ICONS[type] ?? '📡'}</span>
      {name}
    </span>
  );
}

interface FilterBarProps {
  filters: MessageLogFilters;
  channels: Array<{ id: string; name: string; type: string }>;
  onChange: (f: Partial<MessageLogFilters>) => void;
  onReset: () => void;
}

function FilterBar({ filters, channels, onChange, onReset }: FilterBarProps) {
  const [open, setOpen] = useState(false);
  const activeCount = [
    filters.channel_id, filters.channel_type, filters.agent_id,
    filters.status, filters.success !== undefined ? '1' : undefined,
    filters.date_from, filters.date_to,
  ].filter(Boolean).length;

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm font-medium transition-colors
          ${activeCount > 0
            ? 'bg-blue-600/20 border-blue-500/40 text-blue-300'
            : 'bg-gray-800 border-gray-600/50 text-gray-400 hover:text-gray-200 hover:border-gray-500'
          }`}
      >
        <Filter className="w-4 h-4" />
        Filters
        {activeCount > 0 && (
          <span className="bg-blue-500 text-white text-xs w-5 h-5 rounded-full flex items-center justify-center">
            {activeCount}
          </span>
        )}
        <ChevronDown className={`w-3 h-3 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-2 w-96 bg-gray-800 border border-gray-600/50 rounded-xl shadow-2xl shadow-black/50 z-30 p-4 space-y-3">
          {/* Channel */}
          <div>
            <label className="text-xs text-gray-400 font-medium mb-1 block">Channel</label>
            <select 
              value={filters.channel_id ?? ''}
              onChange={e => onChange({ channel_id: e.target.value || undefined })}
              className="w-full bg-gray-700 border border-gray-600/50 rounded-lg px-3 py-1.5 text-sm text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="">All channels</option>
              {channels.map(c => (
                <option key={c.id} value={c.id}>{CHANNEL_ICONS[c.type] ?? '📡'} {c.name}</option>
              ))}
            </select>
          </div>

          {/* Channel type */}
          <div>
            <label className="text-xs text-gray-400 font-medium mb-1 block">Channel Type</label>
            <select
              value={filters.channel_type ?? ''}
              onChange={e => onChange({ channel_type: e.target.value || undefined })}
              className="w-full bg-gray-700 border border-gray-600/50 rounded-lg px-3 py-1.5 text-sm text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="">All types</option>
              {CHANNEL_TYPE_OPTIONS.map(t => (
                <option key={t} value={t}>{CHANNEL_ICONS[t] ?? '📡'} {t}</option>
              ))}
            </select>
          </div>

          {/* Status */}
          <div>
            <label className="text-xs text-gray-400 font-medium mb-1 block">Status</label>
            <div className="flex flex-wrap gap-1.5">
              {(['', 'received', 'processing', 'responded', 'failed'] as const).map(s => (
                <button
                  key={s}
                  onClick={() => onChange({ status: s || undefined, success: undefined })}
                  className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors border
                    ${(filters.status ?? '') === s
                      ? 'bg-blue-600/30 border-blue-500/50 text-blue-300'
                      : 'bg-gray-700 border-gray-600/40 text-gray-400 hover:text-gray-200'
                    }`}
                >
                  {s || 'All'}
                </button>
              ))}
            </div>
          </div>

          {/* Success / Failure quick filters */}
          <div>
            <label className="text-xs text-gray-400 font-medium mb-1 block">Outcome</label>
            <div className="flex gap-1.5">
              {[
                { label: 'Any', value: undefined },
                { label: '✅ Success', value: true },
                { label: '❌ Failures', value: false },
              ].map(opt => (
                <button
                  key={String(opt.value)}
                  onClick={() => onChange({ success: opt.value, status: undefined })}
                  className={`flex-1 py-1 rounded-lg text-xs font-medium transition-colors border
                    ${filters.success === opt.value
                      ? 'bg-blue-600/30 border-blue-500/50 text-blue-300'
                      : 'bg-gray-700 border-gray-600/40 text-gray-400 hover:text-gray-200'
                    }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Date range */}
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-xs text-gray-400 font-medium mb-1 block">From</label>
              <input
                type="datetime-local"
                value={filters.date_from?.slice(0, 16) ?? ''}
                onChange={e => onChange({ date_from: e.target.value ? e.target.value + ':00' : undefined })}
                className="w-full bg-gray-700 border border-gray-600/50 rounded-lg px-2 py-1.5 text-xs text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="text-xs text-gray-400 font-medium mb-1 block">To</label>
              <input
                type="datetime-local"
                value={filters.date_to?.slice(0, 16) ?? ''}
                onChange={e => onChange({ date_to: e.target.value ? e.target.value + ':00' : undefined })}
                className="w-full bg-gray-700 border border-gray-600/50 rounded-lg px-2 py-1.5 text-xs text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* Agent */}
          <div>
            <label className="text-xs text-gray-400 font-medium mb-1 block">Agent ID</label>
            <input
              type="text"
              placeholder="e.g. 10001"
              value={filters.agent_id ?? ''}
              onChange={e => onChange({ agent_id: e.target.value || undefined })}
              className="w-full bg-gray-700 border border-gray-600/50 rounded-lg px-3 py-1.5 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div className="flex justify-end pt-1">
            <button
              onClick={() => { onReset(); setOpen(false); }}
              className="text-xs text-gray-400 hover:text-gray-200 flex items-center gap-1 transition-colors"
            >
              <X className="w-3 h-3" /> Clear all filters
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Message Row ──────────────────────────────────────────────────────────────

interface MessageRowProps {
  msg: ChannelMessage;
  onReplay: (id: string) => Promise<void>;
  replayingId: string | null;
}

function MessageRow({ msg, onReplay, replayingId }: MessageRowProps) {
  const [expanded, setExpanded] = useState(false);
  const isReplaying = replayingId === msg.id;
  const canReplay = msg.status === 'failed' || msg.error_count > 0;

  const ts = new Date(msg.created_at);
  const relativeTime = (() => {
    const diff = (Date.now() - ts.getTime()) / 1000;
    if (diff < 60) return `${Math.floor(diff)}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return ts.toLocaleDateString();
  })();

  return (
    <div
      className={`border rounded-xl overflow-hidden transition-colors ${
        msg.status === 'failed'
          ? 'border-red-500/20 bg-red-500/5 hover:bg-red-500/8'
          : 'border-gray-700/50 bg-gray-800/40 hover:bg-gray-800/70'
      }`}
    >
      {/* Main row */}
      <div
        className="flex items-center gap-3 px-4 py-3 cursor-pointer"
        onClick={() => setExpanded(e => !e)}
      >
        {/* Channel icon */}
        <span className="text-xl flex-shrink-0 w-7 text-center">
          {CHANNEL_ICONS[msg.channel_type] ?? '📡'}
        </span>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm text-gray-200 font-medium truncate max-w-xs">
              {msg.sender_name || msg.sender_id}
            </span>
            <ChannelBadge type={msg.channel_type} name={msg.channel_name} />
            {msg.task_id && (
              <span className="text-xs text-gray-500 font-mono">
                #{msg.task_id.slice(0, 8)}
              </span>
            )}
          </div>
          <p className="text-sm text-gray-400 truncate mt-0.5">
            {msg.content || <em className="text-gray-600">no content</em>}
          </p>
          {msg.last_error && (
            <p className="text-xs text-red-400 truncate mt-0.5 flex items-center gap-1">
              <AlertCircle className="w-3 h-3 flex-shrink-0" /> {msg.last_error}
            </p>
          )}
        </div>

        {/* Right side */}
        <div className="flex items-center gap-3 flex-shrink-0">
          <StatusBadge status={msg.status} />
          <span className="text-xs text-gray-500 w-16 text-right">{relativeTime}</span>

          {canReplay && (
            <button
              onClick={e => { e.stopPropagation(); onReplay(msg.id); }}
              disabled={isReplaying}
              className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-amber-500/15 border border-amber-500/30 text-amber-400 text-xs font-medium hover:bg-amber-500/25 transition-colors disabled:opacity-50"
            >
              {isReplaying
                ? <Loader2 className="w-3 h-3 animate-spin" />
                : <Play className="w-3 h-3" />
              }
              Replay
            </button>
          )}

          <ChevronDown className={`w-4 h-4 text-gray-500 transition-transform ${expanded ? 'rotate-180' : ''}`} />
        </div>
      </div>

      {/* Expanded details */}
      {expanded && (
        <div className="border-t border-gray-700/50 px-4 py-3 bg-gray-900/30 space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { icon: Hash, label: 'Message ID', value: msg.id },
              { icon: MessageSquare, label: 'Type', value: msg.message_type },
              { icon: User, label: 'Sender ID', value: msg.sender_id },
              { icon: Calendar, label: 'Received', value: ts.toLocaleString() },
              ...(msg.assigned_agent_id ? [{ icon: Zap, label: 'Agent', value: msg.assigned_agent_id }] : []),
              ...(msg.task_id ? [{ icon: LayoutGrid, label: 'Task', value: msg.task_id }] : []),
            ].map(({ icon: Icon, label, value }) => (
              <div key={label}>
                <span className="text-xs text-gray-500 flex items-center gap-1 mb-0.5">
                  <Icon className="w-3 h-3" /> {label}
                </span>
                <span className="text-xs text-gray-300 font-mono break-all">{value}</span>
              </div>
            ))}
          </div>

          {msg.content && (
            <div>
              <span className="text-xs text-gray-500 block mb-1">Full Content</span>
              <pre className="text-xs text-gray-300 bg-gray-900/60 rounded-lg p-3 whitespace-pre-wrap break-words max-h-48 overflow-y-auto">
                {msg.content}
              </pre>
            </div>
          )}

          {msg.error_count > 0 && (
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-3.5 h-3.5 text-red-400 flex-shrink-0" />
              <span className="text-xs text-red-400">
                {msg.error_count} error{msg.error_count > 1 ? 's' : ''} recorded
                {msg.last_error && ` — ${msg.last_error}`}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

const DEFAULT_FILTERS: MessageLogFilters = {
  limit: 50,
  offset: 0,
};

export function MessageLogPage() {
  const [messages, setMessages] = useState<ChannelMessage[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<MessageLogFilters>(DEFAULT_FILTERS);
  const [search, setSearch] = useState('');
  const [channels, setChannels] = useState<Array<{ id: string; name: string; type: string }>>([]);
  const [replayingId, setReplayingId] = useState<string | null>(null);
  const [bulkReplaying, setBulkReplaying] = useState(false);
  const searchDebounce = useRef<ReturnType<typeof setTimeout>>();

  // Load channels for filter dropdown
  useEffect(() => {
    api.get('/channels/').then(r => {
      setChannels(
        (r.data.channels ?? []).map((c: any) => ({
          id: c.id,
          name: c.name,
          type: c.type,
        }))
      );
    }).catch(() => {});
  }, []);

  const fetchMessages = useCallback(async (f: MessageLogFilters) => {
    setLoading(true);
    try {
      const data = await channelMessagesApi.getLog(f);
      setMessages(data.messages);
      setTotal(data.total);
    } catch {
      toast.error('Failed to load message log');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMessages(filters);
  }, [filters, fetchMessages]);

  const handleFilterChange = (patch: Partial<MessageLogFilters>) => {
    setFilters(prev => ({ ...prev, ...patch, offset: 0 }));
  };

  const handleSearchChange = (value: string) => {
    setSearch(value);
    clearTimeout(searchDebounce.current);
    searchDebounce.current = setTimeout(() => {
      setFilters(prev => ({ ...prev, search: value || undefined, offset: 0 }));
    }, 400);
  };

  const handleReset = () => {
    setSearch('');
    setFilters(DEFAULT_FILTERS);
  };

  const handleReplay = async (messageId: string) => {
    setReplayingId(messageId);
    try {
      await channelMessagesApi.replayMessage(messageId);
      toast.success('Message re-queued for processing');
      fetchMessages(filters);
    } catch {
      toast.error('Replay failed');
    } finally {
      setReplayingId(null);
    }
  };

  const handleBulkReplay = async () => {
    setBulkReplaying(true);
    try {
      const res = await channelMessagesApi.replayFailed(filters.channel_id);
      toast.success(`Replaying ${res.queued} failed message(s)`);
      setTimeout(() => fetchMessages(filters), 1500);
    } catch {
      toast.error('Bulk replay failed');
    } finally {
      setBulkReplaying(false);
    }
  };

  const failedCount = messages.filter(m => m.status === 'failed' || m.error_count > 0).length;
  const currentPage = Math.floor((filters.offset ?? 0) / (filters.limit ?? 50)) + 1;
  const totalPages = Math.ceil(total / (filters.limit ?? 50));

  const hasActiveFilters = Object.keys(filters).some(
    k => k !== 'limit' && k !== 'offset' && filters[k as keyof MessageLogFilters] !== undefined
  ) || !!search;

  return (
    <div className="flex flex-col h-full min-h-0 bg-gray-900 text-gray-100">
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-gray-700/50 bg-gray-900/80 backdrop-blur-sm">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center">
              <Inbox className="w-4 h-4 text-blue-400" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-gray-100">Message Log</h1>
              <p className="text-xs text-gray-400">
                {total.toLocaleString()} message{total !== 1 ? 's' : ''} across all channels
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {failedCount > 0 && (
              <button
                onClick={handleBulkReplay}
                disabled={bulkReplaying}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-amber-500/15 border border-amber-500/30 text-amber-400 text-sm font-medium hover:bg-amber-500/25 transition-colors disabled:opacity-50"
              >
                {bulkReplaying
                  ? <Loader2 className="w-4 h-4 animate-spin" />
                  : <RotateCcw className="w-4 h-4" />
                }
                Replay {failedCount} Failed
              </button>
            )}
            <button
              onClick={() => fetchMessages(filters)}
              className="p-2 rounded-lg bg-gray-800 border border-gray-600/50 text-gray-400 hover:text-gray-200 transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Filter row */}
        <div className="flex items-center gap-2 mt-3 flex-wrap">
          {/* Search */}
          <div className="relative flex-1 min-w-52">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input
              type="text"
              placeholder="Search messages, senders…"
              value={search}
              onChange={e => handleSearchChange(e.target.value)}
              className="w-full pl-9 pr-3 py-2 bg-gray-800 border border-gray-600/50 rounded-lg text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <FilterBar
            filters={filters}
            channels={channels}
            onChange={handleFilterChange}
            onReset={handleReset}
          />

          {hasActiveFilters && (
            <button
              onClick={handleReset}
              className="flex items-center gap-1 px-2 py-2 rounded-lg text-xs text-gray-400 hover:text-gray-200 transition-colors"
            >
              <X className="w-3.5 h-3.5" /> Clear
            </button>
          )}
        </div>

        {/* Active filter chips */}
        {hasActiveFilters && (
          <div className="flex flex-wrap gap-1.5 mt-2">
            {filters.channel_id && (
              <FilterChip
                label={`Channel: ${channels.find(c => c.id === filters.channel_id)?.name ?? filters.channel_id}`}
                onRemove={() => handleFilterChange({ channel_id: undefined })}
              />
            )}
            {filters.channel_type && (
              <FilterChip label={`Type: ${filters.channel_type}`} onRemove={() => handleFilterChange({ channel_type: undefined })} />
            )}
            {filters.status && (
              <FilterChip label={`Status: ${filters.status}`} onRemove={() => handleFilterChange({ status: undefined })} />
            )}
            {filters.success !== undefined && (
              <FilterChip label={filters.success ? 'Successes only' : 'Failures only'} onRemove={() => handleFilterChange({ success: undefined })} />
            )}
            {filters.date_from && (
              <FilterChip label={`From: ${new Date(filters.date_from).toLocaleDateString()}`} onRemove={() => handleFilterChange({ date_from: undefined })} />
            )}
            {filters.date_to && (
              <FilterChip label={`To: ${new Date(filters.date_to).toLocaleDateString()}`} onRemove={() => handleFilterChange({ date_to: undefined })} />
            )}
            {filters.agent_id && (
              <FilterChip label={`Agent: ${filters.agent_id}`} onRemove={() => handleFilterChange({ agent_id: undefined })} />
            )}
            {search && (
              <FilterChip label={`Search: "${search}"`} onRemove={() => handleSearchChange('')} />
            )}
          </div>
        )}
      </div>

      {/* Message list */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-2">
        {loading && messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-gray-500">
            <Loader2 className="w-8 h-8 animate-spin mb-3" />
            <p className="text-sm">Loading messages…</p>
          </div>
        ) : messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-gray-500">
            <Inbox className="w-10 h-10 mb-3 opacity-30" />
            <p className="text-sm font-medium">No messages found</p>
            {hasActiveFilters && (
              <p className="text-xs mt-1 text-gray-600">Try adjusting or clearing your filters</p>
            )}
          </div>
        ) : (
          messages.map(msg => (
            <MessageRow
              key={msg.id}
              msg={msg}
              onReplay={handleReplay}
              replayingId={replayingId}
            />
          ))
        )}
      </div>

      {/* Pagination */}
      {total > (filters.limit ?? 50) && (
        <div className="flex-shrink-0 flex items-center justify-between px-6 py-3 border-t border-gray-700/50 bg-gray-900/80">
          <span className="text-xs text-gray-500">
            Showing {(filters.offset ?? 0) + 1}–{Math.min((filters.offset ?? 0) + (filters.limit ?? 50), total)} of {total.toLocaleString()}
          </span>
          <div className="flex items-center gap-2">
            <button
              disabled={(filters.offset ?? 0) === 0}
              onClick={() => setFilters(p => ({ ...p, offset: Math.max(0, (p.offset ?? 0) - (p.limit ?? 50)) }))}
              className="p-1.5 rounded-lg bg-gray-800 border border-gray-600/50 text-gray-400 hover:text-gray-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="text-xs text-gray-400 px-2">
              {currentPage} / {totalPages}
            </span>
            <button
              disabled={currentPage >= totalPages}
              onClick={() => setFilters(p => ({ ...p, offset: (p.offset ?? 0) + (p.limit ?? 50) }))}
              className="p-1.5 rounded-lg bg-gray-800 border border-gray-600/50 text-gray-400 hover:text-gray-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Filter chip ──────────────────────────────────────────────────────────────

function FilterChip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-blue-500/15 border border-blue-500/25 text-blue-300 text-xs">
      {label}
      <button onClick={onRemove} className="hover:text-white transition-colors">
        <X className="w-3 h-3" />
      </button>
    </span>
  );
}