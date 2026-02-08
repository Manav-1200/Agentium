import { useState, useEffect } from 'react';
import { Coins, DollarSign, Shield, AlertTriangle } from 'lucide-react';
import { api } from '@/services/api';
import { useAuthStore } from '@/store/authStore';

interface BudgetStatus {
    current_limits: {
        daily_token_limit: number;
        daily_cost_limit: number;
    };
    usage: {
        tokens_used_today: number;
        tokens_remaining: number;
        cost_used_today_usd: number;
        cost_remaining_usd: number;
        cost_percentage_used: number;
        cost_percentage_tokens: number;
    };
    can_modify: boolean;
    optimizer_status: {
        idle_mode_active: boolean;
        time_since_last_activity_seconds: number;
    };
}

export default function BudgetControl() {
    const [budget, setBudget] = useState<BudgetStatus | null>(null);
    const [tokenInput, setTokenInput] = useState('');
    const [costInput, setCostInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [success, setSuccess] = useState(false);
    const { user } = useAuthStore();

    const fetchBudget = async () => {
        try {
            const response = await api.get('/api/v1/admin/budget');
            setBudget(response.data);
            setTokenInput(response.data.current_limits.daily_token_limit.toString());
            setCostInput(response.data.current_limits.daily_cost_limit.toString());
        } catch (error) {
            console.error('Failed to fetch budget:', error);
        }
    };

    useEffect(() => {
        fetchBudget();
    }, []);

    const handleUpdateBudget = async () => {
        setLoading(true);
        setSuccess(false);

        try {
            const response = await api.post('/api/v1/admin/budget', {
                daily_token_limit: parseInt(tokenInput),
                daily_cost_limit: parseFloat(costInput)
            });

            setSuccess(true);
            await fetchBudget();
            setTimeout(() => setSuccess(false), 3000);
        } catch (error: any) {
            console.error('Failed to update budget:', error);
            alert(error.response?.data?.detail || 'Failed to update budget');
        } finally {
            setLoading(false);
        }
    };

    if (!budget) return <div className="text-center p-4">Loading budget control...</div>;

    // CHANGED: Use can_modify from API response instead of checking agentium_id
    const canModifyBudget = budget.can_modify;

    const isOverBudget = budget.usage.cost_percentage_used > 90;
    const isNearLimit = budget.usage.cost_percentage_used > 75;

    return (
        <div className="w-full max-w-2xl border-2 rounded-lg shadow-sm bg-white">
            {/* Header */}
            <div className="flex flex-row items-center justify-between bg-gradient-to-r from-blue-50 to-purple-50 p-6 rounded-t-lg border-b">
                <h2 className="flex items-center gap-2 text-xl font-semibold">
                    <Coins className="h-6 w-6 text-blue-600" />
                    Budget Control Dashboard
                </h2>
                {canModifyBudget && (
                    <div title="Admin Access">
                        <Shield className="h-5 w-5 text-green-600" />
                    </div>
                )}
            </div>

            <div className="space-y-6 p-6">
                {/* Status Badges */}
                {budget.optimizer_status.idle_mode_active && (
                    <div className="bg-yellow-50 border border-yellow-500 rounded-lg p-4 flex items-start gap-3">
                        <AlertTriangle className="h-4 w-4 text-yellow-600 mt-0.5" />
                        <p className="text-sm text-yellow-800">
                            🌙 System is in IDLE MODE - Using local models to save tokens
                        </p>
                    </div>
                )}

                {isOverBudget && (
                    <div className="bg-red-50 border border-red-500 rounded-lg p-4 flex items-start gap-3">
                        <AlertTriangle className="h-4 w-4 text-red-600 mt-0.5" />
                        <p className="text-sm text-red-800">
                            ⚠️ CRITICAL: You have exceeded 90% of your daily budget!
                        </p>
                    </div>
                )}

                {isNearLimit && !isOverBudget && (
                    <div className="bg-amber-50 border border-amber-500 rounded-lg p-4 flex items-start gap-3">
                        <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5" />
                        <p className="text-sm text-amber-800">
                            ⚠️ Warning: You have used {budget.usage.cost_percentage_used}% of your budget
                        </p>
                    </div>
                )}

                {/* Current Limits Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* Token Card */}
                    <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
                        <div className="flex items-center gap-2 text-sm font-medium text-blue-900 mb-2">
                            <Coins className="h-4 w-4" />
                            Token Limit
                        </div>
                        <div className="text-3xl font-bold text-blue-700">
                            {budget.current_limits.daily_token_limit.toLocaleString()}
                        </div>
                        <div className="mt-2">
                            <div className="flex justify-between text-xs text-blue-600 mb-1">
                                <span>Used</span>
                                <span>{budget.usage.cost_percentage_tokens}%</span>
                            </div>
                            <div className="w-full bg-blue-200 rounded-full h-2">
                                <div
                                    className={`h-2 rounded-full transition-all ${isOverBudget ? 'bg-red-500' : isNearLimit ? 'bg-amber-500' : 'bg-blue-500'
                                        }`}
                                    style={{ width: `${Math.min(budget.usage.cost_percentage_tokens, 100)}%` }}
                                />
                            </div>
                            <div className="text-xs text-blue-600 mt-1">
                                {budget.usage.tokens_used_today.toLocaleString()} / {budget.current_limits.daily_token_limit.toLocaleString()} used
                            </div>
                        </div>
                    </div>

                    {/* Cost Card */}
                    <div className="bg-green-50 rounded-lg p-4 border border-green-200">
                        <div className="flex items-center gap-2 text-sm font-medium text-green-900 mb-2">
                            <DollarSign className="h-4 w-4" />
                            Cost Limit (USD)
                        </div>
                        <div className="text-3xl font-bold text-green-700">
                            ${budget.current_limits.daily_cost_limit.toFixed(2)}
                        </div>
                        <div className="mt-2">
                            <div className="flex justify-between text-xs text-green-600 mb-1">
                                <span>Used</span>
                                <span>{budget.usage.cost_percentage_used}%</span>
                            </div>
                            <div className="w-full bg-green-200 rounded-full h-2">
                                <div
                                    className={`h-2 rounded-full transition-all ${isOverBudget ? 'bg-red-500' : isNearLimit ? 'bg-amber-500' : 'bg-green-500'
                                        }`}
                                    style={{ width: `${Math.min(budget.usage.cost_percentage_used, 100)}%` }}
                                />
                            </div>
                            <div className="text-xs text-green-600 mt-1">
                                ${budget.usage.cost_used_today_usd.toFixed(4)} / ${budget.current_limits.daily_cost_limit.toFixed(2)} used
                            </div>
                        </div>
                    </div>
                </div>

                {/* Usage Details */}
                <div className="bg-gray-50 rounded-lg p-4 space-y-2">
                    <div className="flex justify-between text-sm">
                        <span className="text-gray-600">Tokens Remaining:</span>
                        <span className="font-medium">{budget.usage.tokens_remaining.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                        <span className="text-gray-600">Cost Remaining:</span>
                        <span className="font-medium">${budget.usage.cost_remaining_usd.toFixed(4)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                        <span className="text-gray-600">Time Since Last Activity:</span>
                        <span className="font-medium">
                            {Math.floor(budget.optimizer_status.time_since_last_activity_seconds)}s
                        </span>
                    </div>
                </div>

                {/* Update Form - Admin Only */}
                {canModifyBudget ? (
                    <div className="space-y-4 border-t pt-4">
                        <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                            <Shield className="h-4 w-4 text-green-600" />
                            Update Budget Settings
                        </h3>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <label htmlFor="token-limit" className="block text-sm font-medium text-gray-700">
                                    Token Limit
                                </label>
                                <input
                                    id="token-limit"
                                    type="number"
                                    value={tokenInput}
                                    onChange={(e) => setTokenInput(e.target.value)}
                                    min="1000"
                                    step="1000"
                                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                />
                                <p className="text-xs text-gray-500">Minimum: 1,000 tokens</p>
                            </div>

                            <div className="space-y-2">
                                <label htmlFor="cost-limit" className="block text-sm font-medium text-gray-700">
                                    Cost Limit (USD)
                                </label>
                                <input
                                    id="cost-limit"
                                    type="number"
                                    value={costInput}
                                    onChange={(e) => setCostInput(e.target.value)}
                                    min="0"
                                    step="0.1"
                                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                />
                                <p className="text-xs text-gray-500">Maximum: $1,000/day</p>
                            </div>
                        </div>

                        <button
                            onClick={handleUpdateBudget}
                            disabled={loading}
                            className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {loading ? (
                                <span className="flex items-center justify-center gap-2">
                                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                                    Updating...
                                </span>
                            ) : (
                                <span className="flex items-center justify-center gap-2">
                                    <Coins className="h-4 w-4" />
                                    Update Budget
                                </span>
                            )}
                        </button>

                        {success && (
                            <div className="bg-green-50 border border-green-500 rounded-lg p-4 flex items-start gap-3">
                                <Shield className="h-4 w-4 text-green-600 mt-0.5" />
                                <p className="text-sm text-green-700">
                                    ✅ Budget updated successfully!
                                </p>
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="bg-blue-50 border border-blue-500 rounded-lg p-4 flex items-start gap-3">
                        <Shield className="h-4 w-4 text-blue-600 mt-0.5" />
                        <p className="text-sm text-blue-700">
                            Only administrators can modify budget settings.
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
}