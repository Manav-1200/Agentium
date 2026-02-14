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
    Settings,
    Sparkles,
    Shield,
    TrendingUp,
    MoreVertical,
    Play
} from 'lucide-react';
import { modelsApi } from '../services/models';
import { ModelConfigForm } from '../components/models/ModelConfigForm';
import type { ModelConfig } from '../types';
import toast from 'react-hot-toast';

/* ─── Provider meta ────────────────────────────────────────────────── */
const PROVIDER_META: Record<
    string,
    { 
        label: string; 
        color: string; 
        bg: string; 
        gradient: string;
        icon: React.ReactNode 
    }
> = {
    openai: {
        label: 'OpenAI',
        color: 'text-emerald-600 dark:text-emerald-400',
        bg: 'bg-emerald-100 dark:bg-emerald-900/30',
        gradient: 'from-emerald-500 to-teal-600',
        icon: <Sparkles className="w-5 h-5" />,
    },
    anthropic: {
        label: 'Anthropic',
        color: 'text-orange-600 dark:text-orange-400',
        bg: 'bg-orange-100 dark:bg-orange-900/30',
        gradient: 'from-orange-500 to-amber-600',
        icon: <Shield className="w-5 h-5" />,
    },
    gemini: {
        label: 'Gemini',
        color: 'text-blue-600 dark:text-blue-400',
        bg: 'bg-blue-100 dark:bg-blue-900/30',
        gradient: 'from-blue-500 to-indigo-600',
        icon: <TrendingUp className="w-5 h-5" />,
    },
    groq: {
        label: 'Groq',
        color: 'text-purple-600 dark:text-purple-400',
        bg: 'bg-purple-100 dark:bg-purple-900/30',
        gradient: 'from-purple-500 to-fuchsia-600',
        icon: <Zap className="w-5 h-5" />,
    },
    mistral: {
        label: 'Mistral',
        color: 'text-rose-600 dark:text-rose-400',
        bg: 'bg-rose-100 dark:bg-rose-900/30',
        gradient: 'from-rose-500 to-pink-600',
        icon: <Cpu className="w-5 h-5" />,
    },
    together: {
        label: 'Together',
        color: 'text-cyan-600 dark:text-cyan-400',
        bg: 'bg-cyan-100 dark:bg-cyan-900/30',
        gradient: 'from-cyan-500 to-sky-600',
        icon: <Globe className="w-5 h-5" />,
    },
    moonshot: {
        label: 'Moonshot',
        color: 'text-violet-600 dark:text-violet-400',
        bg: 'bg-violet-100 dark:bg-violet-900/30',
        gradient: 'from-violet-500 to-purple-600',
        icon: <Sparkles className="w-5 h-5" />,
    },
    deepseek: {
        label: 'DeepSeek',
        color: 'text-red-600 dark:text-red-400',
        bg: 'bg-red-100 dark:bg-red-900/30',
        gradient: 'from-red-500 to-rose-600',
        icon: <Activity className="w-5 h-5" />,
    },
    local: {
        label: 'Local',
        color: 'text-slate-600 dark:text-slate-400',
        bg: 'bg-slate-100 dark:bg-slate-700/40',
        gradient: 'from-slate-500 to-gray-600',
        icon: <Server className="w-5 h-5" />,
    },
    custom: {
        label: 'Custom',
        color: 'text-yellow-600 dark:text-yellow-400',
        bg: 'bg-yellow-100 dark:bg-yellow-900/30',
        gradient: 'from-yellow-500 to-orange-600',
        icon: <Settings className="w-5 h-5" />,
    },
};

const getProviderMeta = (provider: string) =>
    PROVIDER_META[provider] ?? {
        label: provider,
        color: 'text-blue-600 dark:text-blue-400',
        bg: 'bg-blue-100 dark:bg-blue-900/30',
        gradient: 'from-blue-500 to-indigo-600',
        icon: <Cpu className="w-5 h-5" />,
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

/* ─── Summary stat card ─────────────────────────────────────────────── */
const SummaryCard: React.FC<{
    label: string;
    value: string | number;
    icon: React.ReactNode;
    color: 'blue' | 'green' | 'purple' | 'orange';
}> = ({ label, value, icon, color }) => {
    const colorClasses = {
        blue: {
            bg: 'bg-blue-100 dark:bg-blue-900/30',
            text: 'text-blue-600 dark:text-blue-400'
        },
        green: {
            bg: 'bg-green-100 dark:bg-green-900/30',
            text: 'text-green-600 dark:text-green-400'
        },
        purple: {
            bg: 'bg-purple-100 dark:bg-purple-900/30',
            text: 'text-purple-600 dark:text-purple-400'
        },
        orange: {
            bg: 'bg-orange-100 dark:bg-orange-900/30',
            text: 'text-orange-600 dark:text-orange-400'
        }
    };

    return (
        <div className="bg-white dark:bg-gray-800 p-6 rounded-xl border border-gray-200 dark:border-gray-700 hover:shadow-lg transition-shadow">
            <div className="flex items-center justify-between mb-4">
                <div className={`w-12 h-12 rounded-lg ${colorClasses[color].bg} flex items-center justify-center`}>
                    <span className={colorClasses[color].text}>{icon}</span>
                </div>
                <span className="text-2xl font-bold text-gray-900 dark:text-white">
                    {value}
                </span>
            </div>
            <p className="text-sm font-medium text-gray-600 dark:text-gray-400">
                {label}
            </p>
        </div>
    );
};

/* ─── Main component ───────────────────────────────────────────────── */
export const ModelsPage: React.FC = () => {
    const [configs, setConfigs] = useState<ModelConfig[]>([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [editingConfig, setEditingConfig] = useState<ModelConfig | null>(null);
    const [testingId, setTestingId] = useState<string | null>(null);
    const [deletingId, setDeletingId] = useState<string | null>(null);
    const [fetchingModelsId, setFetchingModelsId] = useState<string | null>(null);
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
            await loadConfigs();
        } catch {
            alert('Test failed');
        } finally {
            setTestingId(null);
        }
    };

    const handleFetchModels = async (id: string) => {
        setFetchingModelsId(id);
        try {
            const result = await modelsApi.fetchModels(id);
            alert(
                `Found ${result.count} models:\n${result.models.slice(0, 10).join('\n')}${result.count > 10 ? '\n...and more' : ''
                }`
            );
            await loadConfigs();
        } catch (err: any) {
            alert('Failed to fetch models: ' + err.message);
        } finally {
            setFetchingModelsId(null);
        }
    };

    const handleSave = async (config: ModelConfig) => {
        await loadConfigs();
        setShowForm(false);
        setEditingConfig(null);
        
        // Clear voice status cache if OpenAI provider was added/updated
        if (config.provider === 'openai') {
            const { voiceApi } = await import('@/services/voiceApi');
            voiceApi.clearStatusCache();
            toast.success('Voice features now available with OpenAI provider!');
        }
    };

    const handleEdit = (config: ModelConfig) => {
        setEditingConfig(config);
        setShowForm(true);
    };

    /* ── Derived summary stats ── */
    const activeCount = configs.filter((c) => c.status === 'active').length;
    const totalRequests = configs.reduce(
        (sum, c) => sum + (c.total_usage?.requests ?? 0),
        0
    );
    const totalTokens = configs.reduce(
        (sum, c) => sum + (c.total_usage?.tokens ?? 0),
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
                    <div className="w-12 h-12 border-4 border-blue-200 dark:border-blue-800 border-t-blue-600 rounded-full animate-spin"></div>
                    <p className="text-gray-600 dark:text-gray-400 text-sm">
                        Loading configurations…
                    </p>
                </div>
            </div>
        );
    }

    /* ── Form View ── */
    if (showForm) {
        return (
            <ModelConfigForm
                initialConfig={editingConfig || undefined}
                onSave={handleSave}
                onCancel={() => {
                    setShowForm(false);
                    setEditingConfig(null);
                }}
            />
        );
    }

    return (
        <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-6">
            <div className="max-w-7xl mx-auto">

                {/* ── Page Header ─────────────────────────────────── */}
                <div className="mb-8">
                    <div className="flex items-center justify-between mb-2">
                        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
                            AI Model Configurations
                        </h1>
                        <button
                            onClick={() => setShowForm(true)}
                            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
                        >
                            <Plus className="w-5 h-5" />
                            <span>Add Provider</span>
                        </button>
                    </div>
                    <p className="text-gray-600 dark:text-gray-400">
                        Connect to powerful AI providers and manage your model fleet
                    </p>
                </div>

                {/* ── Summary Stats ────────────────────────────────── */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                    <SummaryCard
                        label="Total Providers"
                        value={configs.length}
                        icon={<Server className="w-6 h-6" />}
                        color="blue"
                    />
                    <SummaryCard
                        label="Active Providers"
                        value={activeCount}
                        icon={<CheckCircle2 className="w-6 h-6" />}
                        color="green"
                    />
                    <SummaryCard
                        label="Total Tokens"
                        value={totalTokens.toLocaleString()}
                        icon={<BarChart3 className="w-6 h-6" />}
                        color="purple"
                    />
                    <SummaryCard
                        label="Est. Cost"
                        value={`$${totalCost.toFixed(2)}`}
                        icon={<Activity className="w-6 h-6" />}
                        color="orange"
                    />
                </div>

                {/* ── Error Banner ─────────────────────────────────── */}
                {error && (
                    <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-start gap-3">
                        <AlertCircle className="w-5 h-5 text-red-600 dark:text-red-400 shrink-0 mt-0.5" />
                        <div className="flex-1">
                            <p className="font-medium text-red-900 dark:text-red-300">
                                Failed to load configurations
                            </p>
                            <p className="text-sm text-red-700 dark:text-red-400 mt-0.5">
                                {error}
                            </p>
                        </div>
                        <button
                            onClick={loadConfigs}
                            className="px-3 py-1.5 bg-red-100 dark:bg-red-900/30 hover:bg-red-200 dark:hover:bg-red-900/50 text-red-700 dark:text-red-400 rounded-lg text-sm font-medium transition-colors"
                        >
                            Retry
                        </button>
                    </div>
                )}

                {/* ── Configurations Grid ───────────────────────────── */}
                {configs.length === 0 ? (
                    <div className="text-center py-20">
                        <div className="inline-flex items-center justify-center w-20 h-20 bg-gray-100 dark:bg-gray-800 rounded-2xl mb-6">
                            <Settings className="w-10 h-10 text-gray-400 dark:text-gray-500" />
                        </div>
                        <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">No Configurations Yet</h3>
                        <p className="text-gray-600 dark:text-gray-400 mb-8 max-w-md mx-auto">
                            Get started by adding your first AI provider. Connect OpenAI, Claude, Gemini, Groq, or run models locally with Ollama.
                        </p>
                        <button
                            onClick={() => setShowForm(true)}
                            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors inline-flex items-center gap-2"
                        >
                            <Plus className="w-5 h-5" />
                            <span>Add Your First Provider</span>
                        </button>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                        {configs.map((config) => {
                            const meta = getProviderMeta(config.provider);
                            return (
                                <div
                                    key={config.id}
                                    className="group relative bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 hover:shadow-xl transition-all duration-300 hover:-translate-y-1 overflow-hidden"
                                >
                                    {/* Gradient Header Bar - Subtle effect */}
                                    <div className={`h-1 bg-gradient-to-r ${meta.gradient}`}></div>
                                    
                                    <div className="p-6">
                                        {/* Header Row */}
                                        <div className="flex items-start justify-between mb-4">
                                            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg ${meta.bg}`}>
                                                <span className={meta.color}>{meta.icon}</span>
                                                <span className={`text-sm font-semibold ${meta.color}`}>
                                                    {config.provider_name || meta.label}
                                                </span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                {config.is_default && (
                                                    <div className="flex items-center gap-1 px-2 py-1 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 rounded-lg text-xs font-medium border border-green-200 dark:border-green-800">
                                                        <Check className="w-3 h-3" />
                                                        Default
                                                    </div>
                                                )}
                                                <StatusBadge status={config.status} />
                                            </div>
                                        </div>

                                        {/* Config Name */}
                                        <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-3 truncate">
                                            {config.config_name}
                                        </h3>

                                        {/* Model Info */}
                                        <div className="space-y-2 mb-4">
                                            <div className="flex items-center justify-between text-sm">
                                                <span className="text-gray-500 dark:text-gray-400">Model</span>
                                                <span className="font-mono text-xs text-gray-900 dark:text-white bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded-md truncate max-w-[180px]">
                                                    {config.default_model}
                                                </span>
                                            </div>
                                            {config.api_key_masked && (
                                                <div className="flex items-center justify-between text-sm">
                                                    <span className="text-gray-500 dark:text-gray-400">API Key</span>
                                                    <span className="text-xs text-gray-500 dark:text-gray-400 font-mono">
                                                        {config.api_key_masked}
                                                    </span>
                                                </div>
                                            )}
                                        </div>

                                        {/* Available Models Tags */}
                                        {config.available_models && config.available_models.length > 0 && (
                                            <div className="mb-4">
                                                <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">Available Models</div>
                                                <div className="flex flex-wrap gap-1.5">
                                                    {config.available_models.slice(0, 4).map((model) => (
                                                        <span
                                                            key={model}
                                                            className={`text-xs px-2 py-1 rounded-md border font-mono ${model === config.default_model
                                                                    ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-700'
                                                                    : 'bg-gray-50 dark:bg-gray-700/50 text-gray-600 dark:text-gray-400 border-gray-200 dark:border-gray-600'
                                                                }`}
                                                        >
                                                            {model.split('/').pop()?.slice(0, 20)}
                                                        </span>
                                                    ))}
                                                    {config.available_models.length > 4 && (
                                                        <span className="text-xs text-gray-400 dark:text-gray-500 px-2 py-1 bg-gray-50 dark:bg-gray-700/30 rounded-md">
                                                            +{config.available_models.length - 4} more
                                                        </span>
                                                    )}
                                                </div>
                                            </div>
                                        )}

                                        {/* Usage Stats - Subtle gradient */}
                                        <div className="grid grid-cols-3 gap-3 p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg mb-4 border border-gray-100 dark:border-gray-700">
                                            <div className="text-center">
                                                <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Requests</div>
                                                <div className="text-base font-bold text-gray-900 dark:text-white">
                                                    {config.total_usage?.requests?.toLocaleString() || 0}
                                                </div>
                                            </div>
                                            <div className="text-center border-x border-gray-200 dark:border-gray-700">
                                                <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Tokens</div>
                                                <div className="text-base font-bold text-gray-900 dark:text-white">
                                                    {(config.total_usage?.tokens || 0) >= 1000 
                                                        ? `${((config.total_usage?.tokens || 0) / 1000).toFixed(1)}k`
                                                        : config.total_usage?.tokens || 0
                                                    }
                                                </div>
                                            </div>
                                            <div className="text-center">
                                                <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Cost</div>
                                                <div className="text-base font-bold text-emerald-600 dark:text-emerald-400">
                                                    ${(config.total_usage?.cost_usd || 0).toFixed(2)}
                                                </div>
                                            </div>
                                        </div>

                                        {/* Action Buttons */}
                                        <div className="flex gap-2">
                                            {!config.is_default && (
                                                <button
                                                    onClick={() => handleSetDefault(config.id)}
                                                    className="flex-1 px-3 py-2 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-1.5"
                                                    title="Set as default"
                                                >
                                                    <Check className="w-4 h-4" />
                                                    Default
                                                </button>
                                            )}
                                            <button
                                                onClick={() => handleTest(config.id)}
                                                disabled={testingId === config.id}
                                                className="flex-1 px-3 py-2 bg-blue-100 dark:bg-blue-900/30 hover:bg-blue-200 dark:hover:bg-blue-900/50 text-blue-700 dark:text-blue-400 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-1.5 disabled:opacity-50"
                                                title="Test connection"
                                            >
                                                {testingId === config.id ? (
                                                    <RefreshCw className="w-4 h-4 animate-spin" />
                                                ) : (
                                                    <Play className="w-4 h-4" />
                                                )}
                                                Test
                                            </button>
                                            <button
                                                onClick={() => handleFetchModels(config.id)}
                                                disabled={fetchingModelsId === config.id}
                                                className="flex-1 px-3 py-2 bg-purple-100 dark:bg-purple-900/30 hover:bg-purple-200 dark:hover:bg-purple-900/50 text-purple-700 dark:text-purple-400 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-1.5 disabled:opacity-50"
                                                title="Fetch available models"
                                            >
                                                {fetchingModelsId === config.id ? (
                                                    <RefreshCw className="w-4 h-4 animate-spin" />
                                                ) : (
                                                    <RefreshCw className="w-4 h-4" />
                                                )}
                                                Fetch
                                            </button>
                                            <button
                                                onClick={() => handleEdit(config)}
                                                className="px-3 py-2 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 rounded-lg transition-colors"
                                                title="Edit"
                                            >
                                                <Edit2 className="w-4 h-4" />
                                            </button>
                                            <button
                                                onClick={() => handleDelete(config.id)}
                                                disabled={deletingId === config.id}
                                                className="px-3 py-2 bg-red-100 dark:bg-red-900/30 hover:bg-red-200 dark:hover:bg-red-900/50 text-red-700 dark:text-red-400 rounded-lg transition-colors disabled:opacity-50"
                                                title="Delete"
                                            >
                                                {deletingId === config.id ? (
                                                    <RefreshCw className="w-4 h-4 animate-spin" />
                                                ) : (
                                                    <Trash2 className="w-4 h-4" />
                                                )}
                                            </button>
                                        </div>
                                    </div>

                                    {/* Hover Glow Effect - Subtle */}
                                    <div className={`absolute inset-0 bg-gradient-to-r ${meta.gradient} opacity-0 group-hover:opacity-5 transition-opacity duration-300 pointer-events-none`}></div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
};

export default ModelsPage;