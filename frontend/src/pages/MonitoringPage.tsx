/**
 * MonitoringPage — updated with:
 * - Per-monitor dashboard selector (dropdown to switch monitor ID)
 * - Full violations list tab with status/severity filters (GET /violations)
 * - Resolve action on each violation (PATCH /violations/{id}/resolve)
 * - 30-second auto-refresh polling (clearInterval on unmount)
 * - Manual refresh button with spinner
 * - Last-updated timestamp
 * - Active alerts count properly colored red when > 0
 * - Agent health breakdown rendered as mini-cards
 * - WebSocket awareness for live violation push
 */

import React, { useEffect, useState, useRef, useCallback } from 'react';
import { monitoringService } from '../services/monitoring';
import { MonitoringDashboard, ViolationReport, AgentHealthReport } from '../types';
import { useWebSocketStore } from '../store/websocketStore';
import {
    Activity,
    ShieldCheck,
    AlertTriangle,
    Loader2,
    RefreshCw,
    Clock,
    Cpu,
    Zap,
    CheckCircle,
    ChevronDown,
    Filter,
    XCircle,
} from 'lucide-react';

const KNOWN_MONITOR_IDS = ['00001', '00002', '00003'];
const REFRESH_INTERVAL_MS = 30_000;

type Tab = 'dashboard' | 'violations';

// ─── Helpers ─────────────────────────────────────────────────────────────────

function HealthRing({ score }: { score: number }) {
    const color = score >= 90 ? '#22c55e' : score >= 70 ? '#f59e0b' : '#ef4444';
    const r = 20;
    const circ = 2 * Math.PI * r;
    const dashOffset = circ * (1 - score / 100);
    return (
        <svg width="52" height="52" className="rotate-[-90deg]">
            <circle cx="26" cy="26" r={r} stroke="#e5e7eb" strokeWidth="4" fill="none" className="dark:stroke-gray-700" />
            <circle
                cx="26" cy="26" r={r}
                stroke={color} strokeWidth="4" fill="none"
                strokeDasharray={circ}
                strokeDashoffset={dashOffset}
                strokeLinecap="round"
                style={{ transition: 'stroke-dashoffset 0.6s ease' }}
            />
        </svg>
    );
}

function SeverityBadge({ severity }: { severity: string }) {
    const cls =
        severity === 'critical' ? 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300' :
        severity === 'major'    ? 'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300' :
        severity === 'moderate' ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300' :
                                  'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300';
    return (
        <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${cls}`}>
            {severity}
        </span>
    );
}

function StatusBadge({ status }: { status: string }) {
    const cls =
        status === 'open'      ? 'bg-red-50 text-red-600 dark:bg-red-900/30 dark:text-red-400' :
        status === 'resolved'  ? 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                                 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400';
    return (
        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${cls}`}>
            {status}
        </span>
    );
}

// ─── Violations Tab ───────────────────────────────────────────────────────────

interface ViolationsTabProps {
    initialViolations: ViolationReport[];
}

function ViolationsTab({ initialViolations }: ViolationsTabProps) {
    const [violations, setViolations] = useState<ViolationReport[]>(initialViolations);
    const [filterStatus, setFilterStatus] = useState<string>('');
    const [filterSeverity, setFilterSeverity] = useState<string>('');
    const [isLoading, setIsLoading] = useState(false);
    const [resolvingId, setResolvingId] = useState<string | null>(null);
    const [resolveModal, setResolveModal] = useState<{ id: string; open: boolean }>({ id: '', open: false });
    const [resolutionNotes, setResolutionNotes] = useState('');
    const [resolveError, setResolveError] = useState<string | null>(null);

    const fetchViolations = useCallback(async () => {
        setIsLoading(true);
        try {
            const data = await monitoringService.getViolations({
                status: filterStatus || undefined,
                severity: filterSeverity || undefined,
            });
            setViolations(data);
        } catch (err) {
            console.error('Failed to fetch violations:', err);
        } finally {
            setIsLoading(false);
        }
    }, [filterStatus, filterSeverity]);

    useEffect(() => {
        fetchViolations();
    }, [fetchViolations]);

    const openResolveModal = (id: string) => {
        setResolutionNotes('');
        setResolveError(null);
        setResolveModal({ id, open: true });
    };

    const handleResolve = async () => {
        if (!resolutionNotes.trim()) {
            setResolveError('Resolution notes are required.');
            return;
        }
        setResolvingId(resolveModal.id);
        try {
            await monitoringService.resolveViolation(resolveModal.id, resolutionNotes);
            setResolveModal({ id: '', open: false });
            // Optimistically update status
            setViolations(prev =>
                prev.map(v =>
                    v.id === resolveModal.id ? { ...v, status: 'resolved' } : v
                )
            );
        } catch (err: any) {
            setResolveError(err.response?.data?.detail || 'Failed to resolve violation.');
        } finally {
            setResolvingId(null);
        }
    };

    return (
        <div>
            {/* Filters */}
            <div className="flex flex-wrap items-center gap-3 mb-6">
                <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                    <Filter className="w-4 h-4" />
                    <span className="font-medium">Filters:</span>
                </div>

                <select aria-label="Filter status"
                    value={filterStatus}
                    onChange={e => setFilterStatus(e.target.value)}
                    className="text-sm border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-1.5 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                    <option value="">All statuses</option>
                    <option value="open">Open</option>
                    <option value="resolved">Resolved</option>
                    <option value="dismissed">Dismissed</option>
                </select>

                <select aria-label="Filter severity"
                    value={filterSeverity}
                    onChange={e => setFilterSeverity(e.target.value)}
                    className="text-sm border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-1.5 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                    <option value="">All severities</option>
                    <option value="critical">Critical</option>
                    <option value="major">Major</option>
                    <option value="moderate">Moderate</option>
                    <option value="minor">Minor</option>
                </select>

                {(filterStatus || filterSeverity) && (
                    <button
                        onClick={() => { setFilterStatus(''); setFilterSeverity(''); }}
                        className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                    >
                        <XCircle className="w-3.5 h-3.5" /> Clear
                    </button>
                )}

                {isLoading && <Loader2 className="w-4 h-4 animate-spin text-blue-500" />}
            </div>

            {/* Table */}
            {violations.length === 0 ? (
                <div className="text-center py-16">
                    <div className="w-14 h-14 rounded-full bg-green-50 dark:bg-green-900/20 flex items-center justify-center mx-auto mb-3 border border-green-100 dark:border-green-800/40">
                        <ShieldCheck className="w-7 h-7 text-green-500 dark:text-green-400" />
                    </div>
                    <p className="text-gray-900 dark:text-white font-medium mb-1">No violations found</p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Try adjusting filters or check back later</p>
                </div>
            ) : (
                <div className="space-y-3">
                    {violations.map((v: ViolationReport) => (
                        <div
                            key={v.id}
                            className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5 shadow-sm"
                        >
                            <div className="flex items-start justify-between gap-4">
                                <div className="flex-1 min-w-0">
                                    <div className="flex flex-wrap items-center gap-2 mb-2">
                                        <SeverityBadge severity={v.severity} />
                                        <StatusBadge status={v.status} />
                                        <span className="text-xs text-gray-400 dark:text-gray-500 font-mono">{v.type}</span>
                                    </div>
                                    <p className="text-sm text-gray-900 dark:text-gray-100 mb-2">{v.description}</p>
                                    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-400 dark:text-gray-500">
                                        <span>Reporter: <span className="font-mono text-gray-600 dark:text-gray-300">{v.reporter}</span></span>
                                        <span>Violator: <span className="font-mono text-gray-600 dark:text-gray-300">{v.violator}</span></span>
                                        {v.created_at && (
                                            <span>{new Date(v.created_at).toLocaleString()}</span>
                                        )}
                                    </div>
                                </div>

                                {v.status === 'open' && (
                                    <button
                                        onClick={() => openResolveModal(v.id)}
                                        disabled={resolvingId === v.id}
                                        className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-800/60 hover:bg-green-100 dark:hover:bg-green-900/50 transition-colors disabled:opacity-50"
                                    >
                                        {resolvingId === v.id
                                            ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                            : <CheckCircle className="w-3.5 h-3.5" />
                                        }
                                        Resolve
                                    </button>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Resolve Modal */}
            {resolveModal.open && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
                    <div className="bg-white dark:bg-gray-900 rounded-xl shadow-2xl border border-gray-200 dark:border-gray-700 w-full max-w-md p-6">
                        <h3 className="text-base font-bold text-gray-900 dark:text-white mb-1">Resolve Violation</h3>
                        <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                            Provide resolution notes before marking this violation as resolved.
                        </p>
                        <textarea
                            value={resolutionNotes}
                            onChange={e => { setResolutionNotes(e.target.value); setResolveError(null); }}
                            placeholder="Describe how the violation was addressed..."
                            rows={4}
                            className="w-full text-sm border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-2 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-green-500 resize-none"
                        />
                        {resolveError && (
                            <p className="text-xs text-red-600 dark:text-red-400 mt-2">{resolveError}</p>
                        )}
                        <div className="flex justify-end gap-3 mt-4">
                            <button
                                onClick={() => setResolveModal({ id: '', open: false })}
                                className="px-4 py-2 rounded-lg text-sm font-medium text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleResolve}
                                disabled={!!resolvingId}
                                className="px-4 py-2 rounded-lg text-sm font-semibold bg-green-600 hover:bg-green-700 text-white transition-colors disabled:opacity-50 flex items-center gap-2"
                            >
                                {resolvingId ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
                                Confirm Resolve
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export const MonitoringPage: React.FC = () => {
    const [monitorId, setMonitorId] = useState(KNOWN_MONITOR_IDS[0]);
    const [dashboard, setDashboard] = useState<MonitoringDashboard | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
    const [activeTab, setActiveTab] = useState<Tab>('dashboard');
    const timerRef = useRef<NodeJS.Timeout | null>(null);

    // WebSocket: refresh on violation or health events
    const lastMessage = useWebSocketStore(s => s.lastMessage);
    useEffect(() => {
        if (!lastMessage) return;
        const data = lastMessage as any;
        if (
            data.event === 'violation_detected' ||
            data.event === 'health_report' ||
            data.type === 'monitoring_update'
        ) {
            loadDashboard(true);
        }
    }, [lastMessage]);

    const loadDashboard = useCallback(async (silent = false) => {
        if (!silent) setIsLoading(true);
        else setIsRefreshing(true);

        try {
            setError(null);
            const data = await monitoringService.getDashboard(monitorId);
            setDashboard(data);
            setLastUpdated(new Date());
        } catch (err: any) {
            console.error('Monitoring error:', err);
            setError(err.response?.data?.detail || 'Monitoring endpoint not available');
            if (!silent) {
                setDashboard({
                    system_health: 100,
                    active_alerts: 0,
                    agent_health_breakdown: {},
                    latest_health_reports: [],
                    recent_violations: [],
                });
            }
        } finally {
            setIsLoading(false);
            setIsRefreshing(false);
        }
    }, [monitorId]);

    // Reload when monitor changes
    useEffect(() => {
        loadDashboard();
        if (timerRef.current) clearInterval(timerRef.current);
        timerRef.current = setInterval(() => loadDashboard(true), REFRESH_INTERVAL_MS);
        return () => {
            if (timerRef.current) clearInterval(timerRef.current);
        };
    }, [loadDashboard]);

    if (isLoading) {
        return (
            <div className="min-h-screen bg-gray-50 dark:bg-gray-950 flex items-center justify-center">
                <div className="flex flex-col items-center gap-3">
                    <Loader2 className="w-8 h-8 animate-spin text-blue-600 dark:text-blue-400" />
                    <span className="text-sm text-gray-500 dark:text-gray-400">Loading metrics...</span>
                </div>
            </div>
        );
    }

    const systemHealth = dashboard?.system_health ?? 100;
    const activeAlerts = dashboard?.active_alerts || 0;
    const healthReports = dashboard?.latest_health_reports || [];
    const violations = dashboard?.recent_violations || [];
    const healthBreakdown = dashboard?.agent_health_breakdown || {};

    const healthColor =
        systemHealth >= 90
            ? 'text-green-600 dark:text-green-400'
            : systemHealth >= 70
            ? 'text-yellow-600 dark:text-yellow-400'
            : 'text-red-600 dark:text-red-400';

    return (
        <div className="min-h-screen bg-gray-50 dark:bg-gray-950 p-6 transition-colors duration-200">
            <div className="max-w-7xl mx-auto">

                {/* ── Header ─────────────────────────────────────────────── */}
                <div className="mb-8 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-600 to-purple-600 flex items-center justify-center shadow-lg">
                            <Activity className="w-7 h-7 text-white" />
                        </div>
                        <div>
                            <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
                                System Monitoring
                            </h1>
                            <p className="text-gray-500 dark:text-gray-400 text-sm">
                                Real-time oversight of agent operations
                            </p>
                        </div>
                    </div>

                    <div className="flex items-center gap-3">
                        {/* Monitor selector */}
                        <div className="relative flex items-center">
                            <label className="text-xs text-gray-500 dark:text-gray-400 mr-2 hidden sm:block">Monitor:</label>
                            <div className="relative">
                                <select aria-label="Monitor ID"
                                    value={monitorId}
                                    onChange={e => setMonitorId(e.target.value)}
                                    className="appearance-none text-sm border border-gray-200 dark:border-gray-700 rounded-lg pl-3 pr-8 py-1.5 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
                                >
                                    {KNOWN_MONITOR_IDS.map(id => (
                                        <option key={id} value={id}>#{id}</option>
                                    ))}
                                </select>
                                <ChevronDown className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" />
                            </div>
                        </div>

                        {lastUpdated && (
                            <span className="hidden sm:flex items-center gap-1 text-xs text-gray-400 dark:text-gray-500">
                                <Clock className="w-3 h-3" />
                                Updated {lastUpdated.toLocaleTimeString()}
                            </span>
                        )}
                        <button
                            onClick={() => loadDashboard(true)}
                            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 dark:text-gray-400 transition-colors"
                            title="Refresh now"
                        >
                            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
                        </button>
                    </div>
                </div>

                {/* ── Error Notice ────────────────────────────────────────── */}
                {error && (
                    <div className="mb-6 bg-yellow-50 dark:bg-yellow-950/40 border border-yellow-200 dark:border-yellow-800/60 rounded-lg p-4">
                        <div className="flex gap-3">
                            <AlertTriangle className="w-5 h-5 text-yellow-600 dark:text-yellow-400 flex-shrink-0 mt-0.5" />
                            <div>
                                <h3 className="text-sm font-semibold text-yellow-900 dark:text-yellow-300 mb-1">
                                    Monitoring System Notice
                                </h3>
                                <p className="text-sm text-yellow-800 dark:text-yellow-400">
                                    {error}. Displaying cached or default values.
                                </p>
                            </div>
                        </div>
                    </div>
                )}

                {/* ── Tabs ────────────────────────────────────────────────── */}
                <div className="flex gap-1 mb-6 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-1 w-fit shadow-sm">
                    {(['dashboard', 'violations'] as Tab[]).map(tab => (
                        <button
                            key={tab}
                            onClick={() => setActiveTab(tab)}
                            className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-colors ${
                                activeTab === tab
                                    ? 'bg-blue-600 text-white shadow-sm'
                                    : 'text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
                            }`}
                        >
                            {tab === 'violations' && activeAlerts > 0 ? (
                                <span className="flex items-center gap-2">
                                    Violations
                                    <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-red-500 text-white">{activeAlerts}</span>
                                </span>
                            ) : (
                                tab.charAt(0).toUpperCase() + tab.slice(1)
                            )}
                        </button>
                    ))}
                </div>

                {/* ══ Dashboard Tab ══════════════════════════════════════════ */}
                {activeTab === 'dashboard' && (
                    <>
                        {/* Stats Grid */}
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">

                            {/* System Health */}
                            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6 shadow-sm flex items-center gap-4">
                                <div className="relative flex-shrink-0">
                                    <HealthRing score={systemHealth} />
                                    <span className={`absolute inset-0 flex items-center justify-center text-xs font-bold ${healthColor}`}>
                                        {systemHealth}%
                                    </span>
                                </div>
                                <div>
                                    <p className="text-sm text-gray-500 dark:text-gray-400 mb-0.5">System Health</p>
                                    <p className={`text-2xl font-bold ${healthColor}`}>{systemHealth}%</p>
                                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                                        {systemHealth >= 90 ? 'Fully Operational' : systemHealth >= 70 ? 'Degraded' : 'Critical'}
                                    </p>
                                </div>
                            </div>

                            {/* Active Alerts */}
                            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6 shadow-sm">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">Active Alerts</p>
                                        <p className={`text-3xl font-bold ${activeAlerts > 0 ? 'text-red-600 dark:text-red-400' : 'text-gray-900 dark:text-white'}`}>
                                            {activeAlerts}
                                        </p>
                                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                                            {activeAlerts === 0 ? 'No issues detected' : `${activeAlerts} requiring attention`}
                                        </p>
                                    </div>
                                    <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${activeAlerts > 0 ? 'bg-red-100 dark:bg-red-900/30' : 'bg-gray-100 dark:bg-gray-800'}`}>
                                        <AlertTriangle className={`w-6 h-6 ${activeAlerts > 0 ? 'text-red-600 dark:text-red-400' : 'text-gray-400 dark:text-gray-500'}`} />
                                    </div>
                                </div>
                            </div>

                            {/* Agents Reporting */}
                            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6 shadow-sm">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">Agents Reporting</p>
                                        <p className="text-3xl font-bold text-gray-900 dark:text-white">
                                            {healthReports.length}
                                        </p>
                                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                                            {healthReports.filter((r: AgentHealthReport) => r.health_score >= 90).length} healthy
                                        </p>
                                    </div>
                                    <div className="w-12 h-12 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
                                        <Cpu className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Agent Health Breakdown */}
                        {Object.keys(healthBreakdown).length > 0 && (
                            <div className="mb-8">
                                <h2 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-3">
                                    Agent Tier Health
                                </h2>
                                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                                    {Object.entries(healthBreakdown).map(([tier, score]) => (
                                        <div key={tier} className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-3 flex items-center gap-3">
                                            <div className={`w-8 h-8 rounded-md flex items-center justify-center ${
                                                (score as number) >= 90 ? 'bg-green-100 dark:bg-green-900/30' : 'bg-yellow-100 dark:bg-yellow-900/30'
                                            }`}>
                                                <Zap className={`w-4 h-4 ${(score as number) >= 90 ? 'text-green-600 dark:text-green-400' : 'text-yellow-600 dark:text-yellow-400'}`} />
                                            </div>
                                            <div>
                                                <p className="text-xs text-gray-500 dark:text-gray-400 capitalize">{tier}</p>
                                                <p className={`text-sm font-bold ${(score as number) >= 90 ? 'text-green-600 dark:text-green-400' : 'text-yellow-600 dark:text-yellow-400'}`}>
                                                    {score}%
                                                </p>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Panels Row */}
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

                            {/* Recent Violations (summary) */}
                            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm overflow-hidden">
                                <div className="bg-yellow-50 dark:bg-yellow-950/50 border-b border-yellow-100 dark:border-yellow-900/60 px-6 py-4 flex items-center justify-between">
                                    <h2 className="text-base font-bold text-gray-900 dark:text-yellow-100 flex items-center gap-2">
                                        <AlertTriangle className="w-5 h-5 text-yellow-600 dark:text-yellow-400" />
                                        Recent Violations
                                    </h2>
                                    <div className="flex items-center gap-2">
                                        {violations.length > 0 && (
                                            <span className="text-xs px-2 py-0.5 rounded-full bg-yellow-200 dark:bg-yellow-800/60 text-yellow-800 dark:text-yellow-300 font-medium">
                                                {violations.length}
                                            </span>
                                        )}
                                        <button
                                            onClick={() => setActiveTab('violations')}
                                            className="text-xs text-blue-600 dark:text-blue-400 hover:underline font-medium"
                                        >
                                            View all →
                                        </button>
                                    </div>
                                </div>

                                <div className="p-6">
                                    {violations.length > 0 ? (
                                        <div className="space-y-3 max-h-80 overflow-y-auto">
                                            {violations.map((v: ViolationReport) => (
                                                <div
                                                    key={v.id}
                                                    className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700"
                                                >
                                                    <div className="flex items-start justify-between gap-4">
                                                        <div className="flex-1">
                                                            <div className="flex items-center gap-2 mb-1">
                                                                <SeverityBadge severity={v.severity} />
                                                                <StatusBadge status={v.status} />
                                                            </div>
                                                            <p className="text-sm text-gray-900 dark:text-gray-100">{v.description}</p>
                                                            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                                                                {v.created_at ? new Date(v.created_at).toLocaleString() : '—'}
                                                            </p>
                                                        </div>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    ) : (
                                        <div className="text-center py-10">
                                            <div className="w-14 h-14 rounded-full bg-green-50 dark:bg-green-900/20 flex items-center justify-center mx-auto mb-3 border border-green-100 dark:border-green-800/40">
                                                <ShieldCheck className="w-7 h-7 text-green-500 dark:text-green-400" />
                                            </div>
                                            <p className="text-gray-900 dark:text-white font-medium mb-1">No Violations Detected</p>
                                            <p className="text-sm text-gray-500 dark:text-gray-400">All agents operating within guidelines</p>
                                        </div>
                                    )}
                                </div>
                            </div>

                            {/* Agent Health Reports */}
                            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm overflow-hidden">
                                <div className="bg-blue-50 dark:bg-blue-950/50 border-b border-blue-100 dark:border-blue-900/60 px-6 py-4 flex items-center justify-between">
                                    <h2 className="text-base font-bold text-gray-900 dark:text-blue-100 flex items-center gap-2">
                                        <Activity className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                                        Agent Health Reports
                                    </h2>
                                    {healthReports.length > 0 && (
                                        <span className="text-xs px-2 py-0.5 rounded-full bg-blue-200 dark:bg-blue-800/60 text-blue-800 dark:text-blue-300 font-medium">
                                            {healthReports.length}
                                        </span>
                                    )}
                                </div>

                                <div className="p-6">
                                    {healthReports.length > 0 ? (
                                        <div className="space-y-3 max-h-80 overflow-y-auto">
                                            {healthReports.map((report: AgentHealthReport) => {
                                                const isHealthy = report.health_score > 90;
                                                return (
                                                    <div
                                                        key={report.id}
                                                        className="flex items-center gap-4 bg-gray-50 dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700"
                                                    >
                                                        <div className="relative flex-shrink-0">
                                                            <HealthRing score={report.health_score} />
                                                            <span className={`absolute inset-0 flex items-center justify-center text-[10px] font-bold ${isHealthy ? 'text-green-600 dark:text-green-400' : 'text-yellow-600 dark:text-yellow-400'}`}>
                                                                {report.health_score}
                                                            </span>
                                                        </div>
                                                        <div className="flex-1 min-w-0">
                                                            <p className="text-sm font-semibold text-gray-900 dark:text-white truncate">
                                                                Agent #{report.subject}
                                                            </p>
                                                            <p className="text-xs text-gray-500 dark:text-gray-400 capitalize">{report.status}</p>
                                                        </div>
                                                        <div className="text-right flex-shrink-0">
                                                            <div className="text-xs text-gray-500 dark:text-gray-400">Success Rate</div>
                                                            <div className={`text-sm font-bold ${isHealthy ? 'text-green-600 dark:text-green-400' : 'text-yellow-600 dark:text-yellow-400'}`}>
                                                                {report.metrics.success_rate}%
                                                            </div>
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    ) : (
                                        <div className="text-center py-10">
                                            <div className="w-14 h-14 rounded-full bg-blue-50 dark:bg-blue-900/20 flex items-center justify-center mx-auto mb-3 border border-blue-100 dark:border-blue-800/40">
                                                <CheckCircle className="w-7 h-7 text-blue-400 dark:text-blue-500" />
                                            </div>
                                            <p className="text-gray-900 dark:text-white font-medium mb-1">No Health Reports</p>
                                            <p className="text-sm text-gray-500 dark:text-gray-400">Agent monitoring will appear here</p>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    </>
                )}

                {/* ══ Violations Tab ═════════════════════════════════════════ */}
                {activeTab === 'violations' && (
                    <ViolationsTab initialViolations={violations} />
                )}

            </div>
        </div>
    );
};