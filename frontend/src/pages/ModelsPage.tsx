import React, { useEffect, useState } from 'react';
import {
    Plus,
    Trash2,
    Edit2,
    Check,
    AlertCircle,
    Server,
    Activity,
    RefreshCw,
    Cpu,
    Globe,
    Key,
    Zap,
    BarChart3,
    CheckCircle2,
    XCircle,
    Clock,
} from 'lucide-react';
import { modelsApi } from '../services/models';
import { ModelConfigForm } from '../components/models/ModelConfigForm';
import type { ModelConfig } from '../types';

/* ─── Provider meta ────────────────────────────────────────────────── */
const PROVIDER_META: Record<
    string,
    { label: string; color: string; bg: string; icon: React.ReactNode }
> = {
    openai: {
        label: 'OpenAI',
        color: 'text-emerald-600 dark:text-emerald-400',
        bg: 'bg-emerald-100 dark:bg-emerald-900/30',
        icon: <Cpu className="w-4 h-4" />,
    },
    anthropic: {
        label: 'Anthropic',
        color: 'text-orange-600 dark:text-orange-400',
        bg: 'bg-orange-100 dark:bg-orange-900/30',
        icon: <Zap className="w-4 h-4" />,
    },
    gemini: {
        label: 'Gemini',
        color: 'text-blue-600 dark:text-blue-400',
        bg: 'bg-blue-100 dark:bg-blue-900/30',
        icon: <Globe className="w-4 h-4" />,
    },
    groq: {
        label: 'Groq',
        color: 'text-pink-600 dark:text-pink-400',
        bg: 'bg-pink-100 dark:bg-pink-900/30',
        icon: <Activity className="w-4 h-4" />,
    },
    mistral: {
        label: 'Mistral',
        color: 'text-purple-600 dark:text-purple-400',
        bg: 'bg-purple-100 dark:bg-purple-900/30',
        icon: <Cpu className="w-4 h-4" />,
    },
    local: {
        label: 'Local',
        color: 'text-gray-600 dark:text-gray-400',
        bg: 'bg-gray-100 dark:bg-gray-700/40',
        icon: <Server className="w-4 h-4" />,
    },
    custom: {
        label: 'Custom',
        color: 'text-yellow-600 dark:text-yellow-400',
        bg: 'bg-yellow-100 dark:bg-yellow-900/30',
        icon: <Globe className="w-4 h-4" />,
    },
};

const getProviderMeta = (provider: string) =>
    PROVIDER_META[provider] ?? {
        label: provider,
        color: 'text-blue-600 dark:text-blue-400',
        bg: 'bg-blue-100 dark:bg-blue-900/30',
        icon: <Cpu className="w-4 h-4" />,
    };

/* ─── Status badge ─────────────────────────────────────────────────── */
const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
    const map: Record<string, { cls: string; icon: React.ReactNode; label: string }> = {
        active: {
            cls: 'bg-green-100 text-green-700 border-green-200 dark:bg-green-900/30 dark:text-green-400 dark:border-green-800',
            icon: <CheckCircle2 className="w-3 h-3" />,
            label: 'Active',
        },
        testing: {
            cls: 'bg-yellow-100 text-yellow-700 border-yellow-200 dark:bg-yellow-900/30 dark:text-yellow-400 dark:border-yellow-800',
            icon: <Clock className="w-3 h-3 animate-pulse" />,
            label: 'Testing',
        },
        error: {
            cls: 'bg-red-100 text-red-700 border-red-200 dark:bg-red-900/30 dark:text-red-400 dark:border-red-800',
            icon: <XCircle className="w-3 h-3" />,
            label: 'Error',
        },
    };
    const s = map[status] ?? {
        cls: 'bg-gray-100 text-gray-600 border-gray-200 dark:bg-gray-700/40 dark:text-gray-400 dark:border-gray-600',
        icon: <Clock className="w-3 h-3" />,
        label: status ?? 'Unknown',
    };
    return (
        <span
            className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full border ${s.cls}`}
        >
            {s.icon}
            {s.label}
        </span>
    );
};

/* ─── Summary stat card (top row) ─────────────────────────────────── */
const SummaryCard: React.FC<{
    label: string;
    value: string | number;
    icon: React.ReactNode;
    colorBg: string;
    colorText: string;
}> = ({ label, value, icon, colorBg, colorText }) => (
    <div className="bg-white dark:bg-gray-800 p-5 rounded-xl border border-gray-200 dark:border-gray-700 flex items-center gap-4">
        <div className={`w-11 h-11 rounded-lg ${colorBg} flex items-center justify-center shrink-0`}>
            <span className={colorText}>{icon}</span>
        </div>
        <div>
            <p className="text-2xl font-bold text-gray-900 dark:text-white leading-none mb-1">
                {value}
            </p>
            <p className="text-xs font-medium text-gray-500 dark:text-gray-400">{label}</p>
        </div>
    </div>
);

/* ─── Main component ───────────────────────────────────────────────── */
export const ModelsPage: React.FC = () => {
    const [configs, setConfigs] = useState<ModelConfig[]>([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [editingConfig, setEditingConfig] = useState<ModelConfig | null>(null);
    const [testingId, setTestingId] = useState<string | null>(null);
    const [deletingId, setDeletingId] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        loadConfigs();
    }, []);

    const loadConfigs = async () => {
        setLoading(true);
        try {
            setError(null);
            const data = await modelsApi.getConfigs();
            if (!Array.isArray(data)) {
                setConfigs([]);
                setError('Invalid response format from server');
            } else {
                setConfigs(data);
            }
        } catch (err: any) {
            setError(err.message || 'Failed to load configurations');
            setConfigs([]);
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async (id: string) => {
        if (!confirm('Delete this configuration?')) return;
        setDeletingId(id);
        try {
            await modelsApi.deleteConfig(id);
            await loadConfigs();
        } catch {
            alert('Failed to delete');
        } finally {
            setDeletingId(null);
        }
    };

    const handleSetDefault = async (id: string) => {
        try {
            await modelsApi.setDefault(id);
            await loadConfigs();
        } catch {
            alert('Failed to set default');
        }
    };

    const handleTest = async (id: string) => {
        setTestingId(id);
        try {
            const result = await modelsApi.testConfig(id);
            alert(
                result.success
                    ? `✅ Connection successful!\nLatency: ${result.latency_ms}ms\nModel: ${result.model}`
                    : `❌ Connection failed: ${result.error}`
            );
        } catch {
            alert('Test failed');
        } finally {
            setTestingId(null);
        }
    };

    const handleFetchModels = async (id: string) => {
        try {
            const result = await modelsApi.fetchModels(id);
            alert(
                `Found ${result.count} models:\n${result.models.slice(0, 10).join('\n')}${result.count > 10 ? '\n...and more' : ''
                }`
            );
            await loadConfigs();
        } catch (err: any) {
            alert('Failed to fetch models: ' + err.message);
        }
    };

    /* ── Derived summary stats ── */
    const activeCount = configs.filter((c) => c.status === 'active').length;
    const defaultConfig = configs.find((c) => c.is_default);
    const totalRequests = configs.reduce(
        (sum, c) => sum + (c.total_usage?.requests ?? 0),
        0
    );
    const totalCost = configs.reduce(
        (sum, c) => sum + (c.total_usage?.cost_usd ?? 0),
        0
    );

    /* ── Loading skeleton ── */
    if (loading) {
        return (
            <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-6 flex items-center justify-center">
                <div className="flex flex-col items-center gap-3">
                    <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
                    <p className="text-gray-600 dark:text-gray-400 text-sm">
                        Loading configurations…
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-6">
            <div className="max-w-6xl mx-auto">

                {/* ── Page Header ─────────────────────────────────── */}
                <div className="mb-8 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <div>
                        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-1">
                            Model Configurations
                        </h1>
                        <p className="text-gray-500 dark:text-gray-400 text-sm">
                            Manage AI providers: OpenAI, Anthropic, Groq, Mistral, Gemini,
                            Local models, and any OpenAI-compatible API.
                        </p>
                    </div>
                    <button
                        onClick={() => {
                            setEditingConfig(null);
                            setShowForm(true);
                        }}
                        className="inline-flex items-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors shadow-sm shrink-0"
                    >
                        <Plus className="w-4 h-4" />
                        Add Provider
                    </button>
                </div>

                {/* ── Summary Stats ────────────────────────────────── */}
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                    <SummaryCard
                        label="Total Providers"
                        value={configs.length}
                        icon={<Server className="w-5 h-5" />}
                        colorBg="bg-blue-100 dark:bg-blue-900/30"
                        colorText="text-blue-600 dark:text-blue-400"
                    />
                    <SummaryCard
                        label="Active Providers"
                        value={activeCount}
                        icon={<CheckCircle2 className="w-5 h-5" />}
                        colorBg="bg-green-100 dark:bg-green-900/30"
                        colorText="text-green-600 dark:text-green-400"
                    />
                    <SummaryCard
                        label="Total Requests"
                        value={totalRequests.toLocaleString()}
                        icon={<BarChart3 className="w-5 h-5" />}
                        colorBg="bg-purple-100 dark:bg-purple-900/30"
                        colorText="text-purple-600 dark:text-purple-400"
                    />
                    <SummaryCard
                        label="Total Cost"
                        value={`$${totalCost.toFixed(4)}`}
                        icon={<Activity className="w-5 h-5" />}
                        colorBg="bg-yellow-100 dark:bg-yellow-900/30"
                        colorText="text-yellow-600 dark:text-yellow-400"
                    />
                </div>

                {/* ── Error Banner ─────────────────────────────────── */}
                {error && (
                    <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-start gap-3">
                        <AlertCircle className="w-5 h-5 text-red-600 dark:text-red-400 shrink-0 mt-0.5" />
                        <div>
                            <p className="font-medium text-red-900 dark:text-red-300">
                                Failed to load configurations
                            </p>
                            <p className="text-sm text-red-700 dark:text-red-400 mt-0.5">
                                {error}
                            </p>
                            <button
                                onClick={loadConfigs}
                                className="mt-2 text-sm font-medium text-red-700 dark:text-red-400 underline hover:no-underline"
                            >
                                Retry
                            </button>
                        </div>
                    </div>
                )}

                {/* ── Modal ────────────────────────────────────────── */}
                {showForm && (
                    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
                        <div className="w-full max-w-2xl max-h-[90vh] overflow-y-auto">
                            <ModelConfigForm
                                onSave={() => {
                                    setShowForm(false);
                                    setEditingConfig(null);
                                    loadConfigs();
                                }}
                                onCancel={() => {
                                    setShowForm(false);
                                    setEditingConfig(null);
                                }}
                                initialConfig={editingConfig}
                            />
                        </div>
                    </div>
                )}

                {/* ── Configurations List ───────────────────────────── */}
                <div className="space-y-4">
                    {configs.map((config) => {
                        const meta = getProviderMeta(config.provider);
                        return (
                            <div
                                key={config.id}
                                className={`bg-white dark:bg-gray-800 rounded-xl border transition-all ${config.is_default
                                        ? 'border-blue-400 dark:border-blue-600 ring-1 ring-blue-400/30 dark:ring-blue-600/30'
                                        : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 hover:shadow-md'
                                    }`}
                            >
                                <div className="p-6">
                                    <div className="flex justify-between items-start gap-4">
                                        {/* Left — info */}
                                        <div className="flex-1 min-w-0">

                                            {/* Title row */}
                                            <div className="flex items-center gap-2.5 flex-wrap mb-3">
                                                {/* Provider icon pill */}
                                                <span
                                                    className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold ${meta.bg} ${meta.color}`}
                                                >
                                                    {meta.icon}
                                                    {config.provider_name || meta.label}
                                                </span>

                                                <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                                                    {config.config_name}
                                                </h3>

                                                {config.is_default && (
                                                    <span className="px-2 py-0.5 bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 text-xs font-semibold rounded-full border border-blue-200 dark:border-blue-700">
                                                        Default
                                                    </span>
                                                )}

                                                <StatusBadge status={config.status} />
                                            </div>

                                            {/* Model + URL row */}
                                            <div className="flex items-center flex-wrap gap-3 text-sm">
                                                <span className="font-mono text-xs bg-gray-100 dark:bg-gray-700/60 text-gray-700 dark:text-gray-300 px-2.5 py-1 rounded-md border border-gray-200 dark:border-gray-600">
                                                    {config.default_model}
                                                </span>

                                                {config.api_key_masked && (
                                                    <span className="inline-flex items-center gap-1 text-xs text-gray-400 dark:text-gray-500">
                                                        <Key className="w-3 h-3" />
                                                        {config.api_key_masked}
                                                    </span>
                                                )}

                                                {(config.api_base_url || config.local_server_url) && (
                                                    <span className="text-xs text-gray-400 dark:text-gray-500 font-mono truncate max-w-xs">
                                                        {config.api_base_url || config.local_server_url}
                                                    </span>
                                                )}
                                            </div>

                                            {/* Available model tags */}
                                            {config.available_models && config.available_models.length > 0 && (
                                                <div className="mt-3 flex flex-wrap gap-1.5">
                                                    {config.available_models.slice(0, 5).map((model) => (
                                                        <span
                                                            key={model}
                                                            className={`text-xs px-2 py-0.5 rounded-md border font-mono ${model === config.default_model
                                                                    ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-700'
                                                                    : 'bg-gray-50 dark:bg-gray-700/50 text-gray-500 dark:text-gray-400 border-gray-200 dark:border-gray-600'
                                                                }`}
                                                        >
                                                            {model.split('/').pop()?.slice(0, 25)}
                                                        </span>
                                                    ))}
                                                    {config.available_models.length > 5 && (
                                                        <span className="text-xs text-gray-400 dark:text-gray-500 px-2 py-0.5">
                                                            +{config.available_models.length - 5} more
                                                        </span>
                                                    )}
                                                </div>
                                            )}

                                            {/* Usage stats */}
                                            {config.total_usage && (
                                                <div className="mt-4 pt-3 border-t border-gray-100 dark:border-gray-700 flex items-center gap-5 text-xs text-gray-500 dark:text-gray-400 flex-wrap">
                                                    <span className="inline-flex items-center gap-1">
                                                        <Activity className="w-3.5 h-3.5" />
                                                        {(config.total_usage.requests ?? 0).toLocaleString()} requests
                                                    </span>
                                                    <span>
                                                        {(config.total_usage.tokens ?? 0).toLocaleString()} tokens
                                                    </span>
                                                    <span className="font-mono font-semibold text-emerald-600 dark:text-emerald-400">
                                                        ${(config.total_usage.cost_usd ?? 0).toFixed(4)}
                                                    </span>
                                                    {config.last_tested && (
                                                        <span className="text-gray-400 dark:text-gray-500">
                                                            Tested:{' '}
                                                            {new Date(config.last_tested).toLocaleString()}
                                                        </span>
                                                    )}
                                                </div>
                                            )}
                                        </div>

                                        {/* Right — action buttons */}
                                        <div className="flex items-center gap-1 shrink-0">
                                            {/* Set default */}
                                            {!config.is_default && (
                                                <button
                                                    onClick={() => handleSetDefault(config.id)}
                                                    title="Set as default"
                                                    className="p-2 rounded-lg text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 transition-colors"
                                                >
                                                    <Check className="w-4 h-4" />
                                                </button>
                                            )}

                                            {/* Test connection */}
                                            <button
                                                onClick={() => handleTest(config.id)}
                                                disabled={testingId === config.id}
                                                title="Test connection"
                                                className="p-2 rounded-lg text-gray-400 hover:text-green-600 dark:hover:text-green-400 hover:bg-green-50 dark:hover:bg-green-900/30 transition-colors disabled:opacity-40"
                                            >
                                                <RefreshCw
                                                    className={`w-4 h-4 ${testingId === config.id ? 'animate-spin' : ''}`}
                                                />
                                            </button>

                                            {/* Fetch models */}
                                            <button
                                                onClick={() => handleFetchModels(config.id)}
                                                title="Fetch available models"
                                                className="p-2 rounded-lg text-gray-400 hover:text-purple-600 dark:hover:text-purple-400 hover:bg-purple-50 dark:hover:bg-purple-900/30 transition-colors"
                                            >
                                                <Server className="w-4 h-4" />
                                            </button>

                                            {/* Edit */}
                                            <button
                                                onClick={() => {
                                                    setEditingConfig(config);
                                                    setShowForm(true);
                                                }}
                                                title="Edit configuration"
                                                className="p-2 rounded-lg text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 transition-colors"
                                            >
                                                <Edit2 className="w-4 h-4" />
                                            </button>

                                            {/* Delete */}
                                            <button
                                                onClick={() => handleDelete(config.id)}
                                                disabled={deletingId === config.id}
                                                title="Delete configuration"
                                                className="p-2 rounded-lg text-gray-400 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 transition-colors disabled:opacity-40"
                                            >
                                                <Trash2 className="w-4 h-4" />
                                            </button>
                                        </div>
                                    </div>

                                    {/* Error inline */}
                                    {config.status === 'error' && (
                                        <div className="mt-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-center gap-2 text-sm text-red-700 dark:text-red-400">
                                            <AlertCircle className="w-4 h-4 shrink-0" />
                                            Configuration error — please check API key and connection settings.
                                        </div>
                                    )}
                                </div>
                            </div>
                        );
                    })}

                    {/* Empty state */}
                    {configs.length === 0 && !error && (
                        <div className="bg-white dark:bg-gray-800 rounded-xl border-2 border-dashed border-gray-200 dark:border-gray-700 py-16 flex flex-col items-center text-center px-6">
                            <div className="w-14 h-14 rounded-xl bg-gray-100 dark:bg-gray-700 flex items-center justify-center mb-4">
                                <Server className="w-7 h-7 text-gray-400 dark:text-gray-500" />
                            </div>
                            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                                No configurations yet
                            </h3>
                            <p className="text-sm text-gray-500 dark:text-gray-400 mb-6 max-w-md">
                                Add your first AI provider to get started. Supports OpenAI,
                                Anthropic, Groq, Mistral, Gemini, Moonshot (Kimi 2.5), local models,
                                and any OpenAI-compatible API.
                            </p>
                            <button
                                onClick={() => setShowForm(true)}
                                className="inline-flex items-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors"
                            >
                                <Plus className="w-4 h-4" />
                                Add Your First Provider
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default ModelsPage;