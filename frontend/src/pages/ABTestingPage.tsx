// frontend/src/pages/ABTestingPage.tsx
import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  FlaskConical, Plus, X, Play, BarChart3, Clock, DollarSign,
  Trophy, ChevronRight, RefreshCw, Trash2, StopCircle,
  TrendingUp, Zap, CheckCircle2, AlertCircle, Loader2,
  Target, Layers, Activity, Shield
} from 'lucide-react';
import {
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  Radar, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend
} from 'recharts';
import { useAuthStore } from '@/store/authStore';
import { api } from '@/services/api';
import { abTestingApi, ExperimentSummary, ExperimentDetail, ModelComparison } from '@/services/abTesting';

// ── Colour palette ────────────────────────────────────────────────────────────
const STATUS_STYLES: Record<string, { bg: string; text: string; dot: string; darkBg?: string; darkText?: string; darkDot?: string }> = {
  draft:     { bg: 'bg-slate-100',  text: 'text-slate-600',  dot: 'bg-slate-400', darkBg: 'dark:bg-slate-800', darkText: 'dark:text-slate-400', darkDot: 'dark:bg-slate-500' },
  pending:   { bg: 'bg-amber-50',   text: 'text-amber-700',  dot: 'bg-amber-400', darkBg: 'dark:bg-amber-500/10', darkText: 'dark:text-amber-400', darkDot: 'dark:bg-amber-400' },
  running:   { bg: 'bg-blue-50',    text: 'text-blue-700',   dot: 'bg-blue-500 animate-pulse', darkBg: 'dark:bg-blue-500/10', darkText: 'dark:text-blue-400', darkDot: 'dark:bg-blue-400' },
  completed: { bg: 'bg-emerald-50', text: 'text-emerald-700',dot: 'bg-emerald-500', darkBg: 'dark:bg-emerald-500/10', darkText: 'dark:text-emerald-400', darkDot: 'dark:bg-emerald-400' },
  failed:    { bg: 'bg-red-50',     text: 'text-red-700',    dot: 'bg-red-500', darkBg: 'dark:bg-red-500/10', darkText: 'dark:text-red-400', darkDot: 'dark:bg-red-400' },
  cancelled: { bg: 'bg-slate-100',  text: 'text-slate-500',  dot: 'bg-slate-300', darkBg: 'dark:bg-slate-800', darkText: 'dark:text-slate-400', darkDot: 'dark:bg-slate-600' },
};

const MODEL_COLORS = ['#6366f1', '#f59e0b', '#10b981', '#ef4444', '#8b5cf6', '#06b6d4'];

// ── Sub-components ────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const s = STATUS_STYLES[status] ?? STATUS_STYLES.draft;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${s.bg} ${s.text} ${s.darkBg || ''} ${s.darkText || ''}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${s.dot} ${s.darkDot || ''}`} />
      {status}
    </span>
  );
}

function ScorePill({ score, label }: { score: number | undefined; label?: string }) {
  const safeScore = score ?? 0;
  const color = safeScore >= 80 ? 'text-emerald-600 bg-emerald-50 dark:text-emerald-400 dark:bg-emerald-500/10' :
                safeScore >= 60 ? 'text-amber-600 bg-amber-50 dark:text-amber-400 dark:bg-amber-500/10' :
                'text-red-600 bg-red-50 dark:text-red-400 dark:bg-red-500/10';
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${color}`}>
      {label && <span className="font-normal mr-1">{label}</span>}
      {safeScore.toFixed(1)}
    </span>
  );
}

function MetricCard({ icon: Icon, label, value, sub }: {
  icon: React.ElementType; label: string; value: string; sub?: string
}) {
  return (
    <div className="bg-white dark:bg-[#161b27] rounded-xl border border-slate-100 dark:border-[#1e2535] p-4 flex items-center gap-3 shadow-sm dark:shadow-[0_2px_8px_rgba(0,0,0,0.2)]">
      <div className="w-9 h-9 rounded-lg bg-indigo-50 dark:bg-indigo-500/10 flex items-center justify-center shrink-0">
        <Icon className="w-4.5 h-4.5 text-indigo-600 dark:text-indigo-400" size={18} />
      </div>
      <div>
        <p className="text-xs text-slate-400 dark:text-slate-500 font-medium">{label}</p>
        <p className="text-lg font-bold text-slate-800 dark:text-white leading-tight">{value}</p>
        {sub && <p className="text-xs text-slate-400 dark:text-slate-500">{sub}</p>}
      </div>
    </div>
  );
}

// ── Create Experiment Modal ───────────────────────────────────────────────────

interface CreateModalProps {
  onClose: () => void;
  onCreated: () => void;
}

function CreateExperimentModal({ onClose, onCreated }: CreateModalProps) {
  const [name, setName] = useState('');
  const [taskTemplate, setTaskTemplate] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [iterations, setIterations] = useState(1);
  const [selectedConfigs, setSelectedConfigs] = useState<string[]>([]);

  const { data: modelsData } = useQuery({
    queryKey: ['model-configs'],
    queryFn: async () => {
      const res = await api.get('/api/v1/models/configs');
      return res.data;
    },
  });
  
  const models = Array.isArray(modelsData) ? modelsData : [];

  const { mutate: create, isPending } = useMutation({
    mutationFn: () => abTestingApi.createExperiment({
      name,
      task_template: taskTemplate,
      config_ids: selectedConfigs,
      description: '',
      system_prompt: systemPrompt || undefined,
      iterations,
    }),
    onSuccess: () => { onCreated(); onClose(); },
  });

  const toggleConfig = (id: string) =>
    setSelectedConfigs(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );

  const isValid = name.trim() && taskTemplate.trim() && selectedConfigs.length >= 2;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 dark:bg-black/80 backdrop-blur-sm">
      <div className="bg-white dark:bg-[#161b27] rounded-2xl shadow-2xl dark:shadow-[0_25px_50px_-12px_rgba(0,0,0,0.5)] w-full max-w-2xl max-h-[90vh] overflow-y-auto border border-slate-100 dark:border-[#1e2535]">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-100 dark:border-[#1e2535]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-600 dark:bg-indigo-500 flex items-center justify-center shadow-lg shadow-indigo-500/25 dark:shadow-indigo-500/20">
              <FlaskConical className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900 dark:text-white">New Experiment</h2>
              <p className="text-xs text-slate-400 dark:text-slate-500">Compare models side-by-side</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-slate-100 dark:hover:bg-[#1e2535] rounded-lg transition-colors">
            <X className="w-4 h-4 text-slate-400 dark:text-slate-500" />
          </button>
        </div>

        <div className="p-6 space-y-5">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">Experiment Name</label>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="e.g. GPT-4 vs Claude Sonnet - Code Quality"
              className="w-full px-3 py-2.5 bg-white dark:bg-[#0f1117] border border-slate-200 dark:border-[#1e2535] rounded-xl text-sm text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent dark:focus:ring-indigo-400"
            />
          </div>

          {/* Task Template */}
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">Task / Prompt</label>
            <textarea
              value={taskTemplate}
              onChange={e => setTaskTemplate(e.target.value)}
              placeholder="Write the task or prompt to test across all models..."
              rows={4}
              className="w-full px-3 py-2.5 bg-white dark:bg-[#0f1117] border border-slate-200 dark:border-[#1e2535] rounded-xl text-sm text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none dark:focus:ring-indigo-400"
            />
          </div>

          {/* System Prompt (optional) */}
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">
              System Prompt <span className="text-slate-400 dark:text-slate-500 font-normal">(optional)</span>
            </label>
            <textarea
              value={systemPrompt}
              onChange={e => setSystemPrompt(e.target.value)}
              placeholder="Optional system context for all models..."
              rows={2}
              className="w-full px-3 py-2.5 bg-white dark:bg-[#0f1117] border border-slate-200 dark:border-[#1e2535] rounded-xl text-sm text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none dark:focus:ring-indigo-400"
            />
          </div>

          {/* Model Selection */}
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">
              Select Models to Compare <span className="text-slate-400 dark:text-slate-500">(pick 2+)</span>
            </label>
              {!Array.isArray(models) || models.length === 0 ? (
                <p className="text-sm text-slate-400 dark:text-slate-500 italic">No model configs found. Add models in the Models page first.</p>
              ) : (
                <div className="grid grid-cols-2 gap-2">
                  {models.map((m: any, i: number) => {
                  const selected = selectedConfigs.includes(m.id);
                  return (
                    <button
                      key={m.id}
                      onClick={() => toggleConfig(m.id)}
                      className={`flex items-center gap-2.5 p-3 rounded-xl border-2 text-left transition-all ${
                        selected
                          ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-500/10'
                          : 'border-slate-200 dark:border-[#1e2535] hover:border-slate-300 dark:hover:border-[#2a3347] bg-white dark:bg-[#0f1117]'
                      }`}
                    >
                      <div
                        className="w-3 h-3 rounded-full shrink-0"
                        style={{ backgroundColor: MODEL_COLORS[i % MODEL_COLORS.length] }}
                      />
                      <div className="min-w-0">
                        <p className={`text-sm font-medium truncate ${selected ? 'text-indigo-700 dark:text-indigo-400' : 'text-slate-700 dark:text-slate-300'}`}>
                          {m.default_model || m.name || m.provider}
                        </p>
                        <p className="text-xs text-slate-400 dark:text-slate-500 truncate">{m.provider}</p>
                      </div>
                      {selected && <CheckCircle2 className="w-4 h-4 text-indigo-600 dark:text-indigo-400 ml-auto shrink-0" />}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Iterations */}
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">
              Iterations per Model
              <span className="text-slate-400 dark:text-slate-500 font-normal ml-1.5">(more = better stats, slower)</span>
            </label>
            <div className="flex gap-2">
              {[1, 2, 3, 5].map(n => (
                <button
                  key={n}
                  onClick={() => setIterations(n)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium border-2 transition-all ${
                    iterations === n
                      ? 'border-indigo-500 bg-indigo-50 text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-400 dark:border-indigo-400'
                      : 'border-slate-200 text-slate-600 dark:border-[#1e2535] dark:text-slate-400 hover:border-slate-300 dark:hover:border-[#2a3347]'
                  }`}
                >
                  {n}×
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-6 border-t border-slate-100 dark:border-[#1e2535]">
          <p className="text-xs text-slate-400 dark:text-slate-500">
            {selectedConfigs.length} model{selectedConfigs.length !== 1 ? 's' : ''} selected
            · {selectedConfigs.length * iterations} total runs
          </p>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-[#1e2535] rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={() => create()}
              disabled={!isValid || isPending}
              className="flex items-center gap-2 px-5 py-2 bg-indigo-600 dark:bg-indigo-500 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 dark:hover:bg-indigo-400 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-md shadow-indigo-500/25 dark:shadow-indigo-500/20"
            >
              {isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              {isPending ? 'Starting...' : 'Run Experiment'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Experiment Detail Panel ───────────────────────────────────────────────────

function ExperimentDetailPanel({
  experimentId,
  onClose,
}: {
  experimentId: string;
  onClose: () => void;
}) {
  const { data: exp, isLoading, refetch } = useQuery({
    queryKey: ['experiment', experimentId],
    queryFn: () => abTestingApi.getExperiment(experimentId),
    refetchInterval: (query) => {
      const d = query.state.data;
      if (!d || d.status === 'running' || d.status === 'pending') return 3000;
      return false;
    },
  });

  const queryClient = useQueryClient();
  const { mutate: cancelExp } = useMutation({
    mutationFn: () => abTestingApi.cancelExperiment(experimentId),
    onSuccess: () => { refetch(); queryClient.invalidateQueries({ queryKey: ['experiments'] }); },
  });

  if (isLoading || !exp) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 animate-spin text-indigo-500" />
      </div>
    );
  }

  const models = exp.comparison?.model_comparisons?.models ?? [];

  const radarData = models.length > 0
    ? ['Quality', 'Cost Efficiency', 'Speed', 'Reliability'].map(metric => {
        const entry: Record<string, any> = { metric };
        models.forEach((m, i) => {
          const maxCost = Math.max(...models.map(x => x.avg_cost_usd || 0.0001));
          const maxLat = Math.max(...models.map(x => x.avg_latency_ms || 1));
          if (metric === 'Quality') entry[m.model_name] = m.avg_quality_score ?? 0;
          if (metric === 'Cost Efficiency') entry[m.model_name] = (1 - ((m.avg_cost_usd ?? 0) / maxCost)) * 100;
          if (metric === 'Speed') entry[m.model_name] = (1 - ((m.avg_latency_ms ?? 0) / maxLat)) * 100;
          if (metric === 'Reliability') entry[m.model_name] = m.success_rate ?? 0;
        });
        return entry;
      })
    : [];

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-black/60 dark:bg-black/80 backdrop-blur-sm">
      <div className="bg-white dark:bg-[#161b27] w-full sm:rounded-2xl shadow-2xl dark:shadow-[0_25px_50px_-12px_rgba(0,0,0,0.5)] max-w-4xl max-h-[92vh] overflow-y-auto border border-slate-100 dark:border-[#1e2535]">
        {/* Header */}
        <div className="sticky top-0 bg-white dark:bg-[#161b27] border-b border-slate-100 dark:border-[#1e2535] px-6 py-4 flex items-center justify-between z-10">
          <div className="flex items-center gap-3">
            <StatusBadge status={exp.status} />
            <h2 className="font-bold text-slate-900 dark:text-white">{exp.name}</h2>
          </div>
          <div className="flex items-center gap-2">
            {(exp.status === 'running' || exp.status === 'pending') && (
              <button
                onClick={() => cancelExp()}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-500/10 rounded-lg border border-red-200 dark:border-red-500/20 transition-colors"
              >
                <StopCircle className="w-3.5 h-3.5" />
                Cancel
              </button>
            )}
            <button
              onClick={() => refetch()}
              className="p-2 hover:bg-slate-100 dark:hover:bg-[#1e2535] rounded-lg transition-colors"
            >
              <RefreshCw className="w-4 h-4 text-slate-400 dark:text-slate-500" />
            </button>
            <button onClick={onClose} className="p-2 hover:bg-slate-100 dark:hover:bg-[#1e2535] rounded-lg transition-colors">
              <X className="w-4 h-4 text-slate-400 dark:text-slate-500" />
            </button>
          </div>
        </div>

        <div className="p-6 space-y-6">
          {/* Progress bar while running */}
          {(exp.status === 'running' || exp.status === 'pending') && (
            <div>
              <div className="flex justify-between text-xs text-slate-400 dark:text-slate-500 mb-1.5">
                <span>Running models...</span>
                <span>{exp.progress}%</span>
              </div>
              <div className="h-2 bg-slate-100 dark:bg-[#0f1117] rounded-full overflow-hidden">
                <div
                  className="h-full bg-indigo-500 dark:bg-indigo-400 rounded-full transition-all duration-500"
                  style={{ width: `${exp.progress}%` }}
                />
              </div>
            </div>
          )}

          {/* Winner banner */}
          {exp.comparison?.winner && (
            <div className="relative overflow-hidden bg-gradient-to-r from-indigo-600 to-violet-600 dark:from-indigo-500 dark:to-violet-500 rounded-2xl p-5 text-white shadow-lg shadow-indigo-500/25 dark:shadow-indigo-500/20">
              <div className="absolute inset-0 opacity-10">
                <div className="absolute -right-8 -top-8 w-40 h-40 rounded-full bg-white" />
                <div className="absolute -left-4 -bottom-4 w-24 h-24 rounded-full bg-white" />
              </div>
              <div className="relative flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <Trophy className="w-4 h-4 text-amber-300" />
                    <span className="text-sm font-medium text-indigo-200">Winner</span>
                  </div>
                  <p className="text-2xl font-bold">{exp.comparison.winner.model ?? 'Unknown'}</p>
                  <p className="text-sm text-indigo-200 mt-1 max-w-lg">{exp.comparison.winner.reason ?? ''}</p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-indigo-300">Confidence</p>
                  <p className="text-3xl font-black">{(exp.comparison.winner.confidence ?? 0).toFixed(0)}%</p>
                </div>
              </div>
            </div>
          )}

          {/* Charts */}
          {models.length >= 2 && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Radar */}
              <div className="bg-slate-50 dark:bg-[#0f1117] rounded-xl p-4 border border-slate-100 dark:border-[#1e2535]">
                <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-3 flex items-center gap-2">
                  <Activity className="w-4 h-4 text-indigo-500 dark:text-indigo-400" />
                  Performance Radar
                </h3>
                <ResponsiveContainer width="100%" height={240}>
                  <RadarChart data={radarData}>
                    <PolarGrid stroke="#e2e8f0" />
                    <PolarAngleAxis dataKey="metric" tick={{ fontSize: 11, fill: '#64748b' }} />
                    <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
                    {models.map((m, i) => (
                      <Radar
                        key={m.model_name}
                        name={m.model_name}
                        dataKey={m.model_name}
                        stroke={MODEL_COLORS[i % MODEL_COLORS.length]}
                        fill={MODEL_COLORS[i % MODEL_COLORS.length]}
                        fillOpacity={0.15}
                        strokeWidth={2}
                      />
                    ))}
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Tooltip 
                      contentStyle={{ 
                        backgroundColor: 'rgba(255, 255, 255, 0.95)', 
                        border: '1px solid #e2e8f0',
                        borderRadius: '8px',
                        boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
                      }}
                    />
                  </RadarChart>
                </ResponsiveContainer>
              </div>

              {/* Cost & Latency Bar */}
              <div className="bg-slate-50 dark:bg-[#0f1117] rounded-xl p-4 border border-slate-100 dark:border-[#1e2535]">
                <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-3 flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-indigo-500 dark:text-indigo-400" />
                  Cost & Latency
                </h3>
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={models} margin={{ left: -15 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="model_name" tick={{ fontSize: 10, fill: '#94a3b8' }} />
                    <YAxis yAxisId="left" tick={{ fontSize: 10, fill: '#94a3b8' }} />
                    <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 10, fill: '#94a3b8' }} />
                    <Tooltip
                      formatter={((value: number | undefined, name: string | undefined) => [
                        name === 'avg_cost_usd'
                          ? `$${(value ?? 0).toFixed(6)}`
                          : `${value ?? 0}ms`,
                        name === 'avg_cost_usd' ? 'Avg Cost' : 'Avg Latency',
                      ]) as any}
                      contentStyle={{ 
                        backgroundColor: 'rgba(255, 255, 255, 0.95)', 
                        border: '1px solid #e2e8f0',
                        borderRadius: '8px'
                      }}
                    />
                    <Bar yAxisId="left" dataKey="avg_cost_usd" fill="#6366f1" name="avg_cost_usd" radius={[4, 4, 0, 0]} />
                    <Bar yAxisId="right" dataKey="avg_latency_ms" fill="#f59e0b" name="avg_latency_ms" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Comparison Table */}
          {models.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-3 flex items-center gap-2">
                <Layers className="w-4 h-4 text-indigo-500 dark:text-indigo-400" />
                Detailed Comparison
              </h3>
              <div className="overflow-x-auto rounded-xl border border-slate-100 dark:border-[#1e2535]">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="bg-slate-50 dark:bg-[#0f1117]">
                      <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">Model</th>
                      <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">Quality</th>
                      <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">Cost</th>
                      <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">Latency</th>
                      <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">Tokens</th>
                      <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">Success</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50 dark:divide-[#1e2535]">
                    {[...models]
                      .sort((a, b) => (b.avg_quality_score ?? 0) - (a.avg_quality_score ?? 0))
                      .map((m, i) => {
                        const isWinner = m.model_name === exp.comparison?.winner?.model;
                        return (
                          <tr key={m.config_id} className={isWinner ? 'bg-indigo-50/50 dark:bg-indigo-500/5' : 'bg-white dark:bg-[#161b27] hover:bg-slate-50 dark:hover:bg-[#1e2535]'}>
                            <td className="px-4 py-3">
                              <div className="flex items-center gap-2">
                                <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: MODEL_COLORS[i % MODEL_COLORS.length] }} />
                                <span className={`font-medium ${isWinner ? 'text-indigo-700 dark:text-indigo-400' : 'text-slate-800 dark:text-slate-200'}`}>{m.model_name}</span>
                                {isWinner && <Trophy className="w-3.5 h-3.5 text-amber-500" />}
                              </div>
                            </td>
                            <td className="px-4 py-3 text-right">
                              <ScorePill score={m.avg_quality_score} />
                            </td>
                            <td className="px-4 py-3 text-right text-slate-600 dark:text-slate-400 font-mono text-xs">
                              ${m.avg_cost_usd?.toFixed(6) ?? '—'}
                            </td>
                            <td className="px-4 py-3 text-right text-slate-600 dark:text-slate-400">
                              {m.avg_latency_ms?.toLocaleString() ?? '—'}ms
                            </td>
                            <td className="px-4 py-3 text-right text-slate-600 dark:text-slate-400">
                              {m.avg_tokens ? Math.round(m.avg_tokens).toLocaleString() : '—'}
                            </td>
                            <td className="px-4 py-3 text-right">
                              <span className={`text-xs font-semibold ${(m.success_rate ?? 0) >= 80 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
                                {(m.success_rate ?? 0).toFixed(0)}%
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Individual Runs */}
          <div>
            <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-3 flex items-center gap-2">
              <Target className="w-4 h-4 text-indigo-500 dark:text-indigo-400" />
              Individual Runs ({exp.runs?.length ?? 0})
            </h3>
            <div className="space-y-2">
              {exp.runs?.map((run, i) => (
                <div key={run.id} className="bg-slate-50 dark:bg-[#0f1117] rounded-xl p-4 border border-slate-100 dark:border-[#1e2535]">
                  <div className="flex flex-wrap items-center gap-2 mb-2">
                    <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: MODEL_COLORS[i % MODEL_COLORS.length] }} />
                    <span className="font-medium text-sm text-slate-800 dark:text-slate-200">{run.model}</span>
                    <StatusBadge status={run.status} />
                    {run.quality_score != null && <ScorePill score={run.quality_score} label="Q" />}
                    {run.latency_ms != null && (
                      <span className="text-xs text-slate-400 dark:text-slate-500">{run.latency_ms.toLocaleString()}ms</span>
                    )}
                    {run.cost_usd != null && (
                      <span className="text-xs text-slate-400 dark:text-slate-500">${run.cost_usd.toFixed(6)}</span>
                    )}
                  </div>
                  {run.output_preview && (
                    <p className="text-xs text-slate-500 dark:text-slate-400 font-mono leading-relaxed bg-white dark:bg-[#161b27] rounded-lg p-2.5 border border-slate-100 dark:border-[#1e2535] line-clamp-3">
                      {run.output_preview}
                    </p>
                  )}
                  {run.error_message && (
                    <p className="text-xs text-red-500 dark:text-red-400 mt-1">{run.error_message}</p>
                  )}
                </div>
              ))}
              {(!exp.runs || exp.runs.length === 0) && (
                <p className="text-sm text-slate-400 dark:text-slate-500 text-center py-6">No runs yet.</p>
              )}
            </div>
          </div>

          {/* Task preview */}
          <div>
            <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2">Task Template</h3>
            <div className="bg-slate-50 dark:bg-[#0f1117] rounded-xl p-4 text-sm text-slate-600 dark:text-slate-400 font-mono whitespace-pre-wrap border border-slate-100 dark:border-[#1e2535]">
              {exp.task_template}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Experiment Card ───────────────────────────────────────────────────────────

function ExperimentCard({
  experiment,
  onClick,
  onDelete,
}: {
  experiment: ExperimentSummary;
  onClick: () => void;
  onDelete: (e: React.MouseEvent) => void;
}) {
  return (
    <div
      onClick={onClick}
      className="bg-white dark:bg-[#161b27] border border-slate-100 dark:border-[#1e2535] rounded-2xl p-5 cursor-pointer hover:shadow-md dark:hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)] hover:border-indigo-100 dark:hover:border-indigo-500/30 transition-all group"
    >
      <div className="flex items-start justify-between mb-3">
        <StatusBadge status={experiment.status} />
        <button
          onClick={onDelete}
          className="p-1.5 rounded-lg opacity-0 group-hover:opacity-100 hover:bg-red-50 dark:hover:bg-red-500/10 transition-all"
        >
          <Trash2 className="w-3.5 h-3.5 text-red-400 dark:text-red-400" />
        </button>
      </div>

      <h3 className="font-semibold text-slate-900 dark:text-white text-sm leading-tight mb-3">{experiment.name}</h3>

      <div className="flex items-center gap-4 text-xs text-slate-400 dark:text-slate-500 mb-3">
        <span className="flex items-center gap-1">
          <Layers className="w-3.5 h-3.5" />
          {experiment.models_tested} models
        </span>
        {experiment.created_at && (
          <span className="flex items-center gap-1">
            <Clock className="w-3.5 h-3.5" />
            {new Date(experiment.created_at).toLocaleDateString()}
          </span>
        )}
      </div>

      {/* Progress */}
      <div>
        <div className="flex justify-between text-xs text-slate-400 dark:text-slate-500 mb-1">
          <span>Progress</span>
          <span>{experiment.progress}%</span>
        </div>
        <div className="h-1.5 bg-slate-100 dark:bg-[#0f1117] rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              experiment.status === 'completed' ? 'bg-emerald-400 dark:bg-emerald-500' :
              experiment.status === 'failed' ? 'bg-red-400 dark:bg-red-500' :
              experiment.status === 'running' ? 'bg-indigo-500 dark:bg-indigo-400' :
              'bg-slate-300 dark:bg-slate-600'
            }`}
            style={{ width: `${experiment.progress}%` }}
          />
        </div>
      </div>

      <div className="mt-3 flex items-center text-xs text-indigo-500 dark:text-indigo-400 font-medium opacity-0 group-hover:opacity-100 transition-opacity">
        View details <ChevronRight className="w-3.5 h-3.5 ml-0.5" />
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export function ABTestingPage() {
  const { user } = useAuthStore();
  const [showCreate, setShowCreate] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('');

  const queryClient = useQueryClient();

  // ── Access Control ─────────────────────────────────────────────────────────
  const isAdmin = user?.isSovereign || user?.is_admin || false;
  
  if (!isAdmin) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-[#0f1117] flex items-center justify-center p-6">
        <div className="text-center">
          <div className="w-20 h-20 bg-red-100 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 rounded-2xl flex items-center justify-center mx-auto mb-5 shadow-sm dark:shadow-[0_2px_16px_rgba(0,0,0,0.25)]">
            <Shield className="w-9 h-9 text-red-600 dark:text-red-400" />
          </div>
          <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">Access Denied</h2>
          <p className="text-slate-500 dark:text-slate-400 text-sm">
            Only admin users can access A/B Testing.
          </p>
        </div>
      </div>
    );
  }

  const { data: experimentsData, isLoading, refetch } = useQuery({
    queryKey: ['experiments', statusFilter],
    queryFn: async () => {
      const res = await abTestingApi.listExperiments(statusFilter || undefined);
      return res;
    },
    refetchInterval: (query) => {
      const d = query.state.data;
      const hasRunning = Array.isArray(d) && d.some(
        (e: ExperimentSummary) => e.status === 'running' || e.status === 'pending'
      );
      return hasRunning ? 4000 : 30000;
    },
  });

  const experiments = Array.isArray(experimentsData) ? experimentsData : [];

  const { data: statsData } = useQuery({
    queryKey: ['ab-stats'],
    queryFn: async () => {
      const res = await abTestingApi.getStats();
      return res;
    },
    refetchInterval: 30000,
  });

  const stats = statsData || null;

  const { mutate: deleteExp } = useMutation({
    mutationFn: (id: string) => abTestingApi.deleteExperiment(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['experiments'] }),
  });

  const FILTERS = ['', 'running', 'completed', 'failed'];

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-[#0f1117]">
      <div className="max-w-6xl mx-auto px-4 py-8 space-y-6">

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-2xl bg-indigo-600 dark:bg-indigo-500 flex items-center justify-center shadow-lg shadow-indigo-200 dark:shadow-indigo-500/20">
              <FlaskConical className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-900 dark:text-white">A/B Model Testing</h1>
              <p className="text-sm text-slate-400 dark:text-slate-500">Compare AI models on cost, speed &amp; quality</p>
            </div>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 dark:bg-indigo-500 text-white text-sm font-medium rounded-xl hover:bg-indigo-700 dark:hover:bg-indigo-400 shadow-sm transition-colors shadow-indigo-200 dark:shadow-indigo-500/20"
          >
            <Plus className="w-4 h-4" />
            New Experiment
          </button>
        </div>

        {/* Stats row */}
        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <MetricCard icon={FlaskConical} label="Total Experiments" value={String(stats.total_experiments)} />
            <MetricCard icon={CheckCircle2} label="Completed" value={String(stats.completed_experiments)} />
            <MetricCard icon={Activity} label="Model Runs" value={(stats.total_model_runs ?? 0).toLocaleString()} />
            <MetricCard icon={TrendingUp} label="Recommendations" value={String(stats.cached_recommendations)} />
          </div>
        )}

        {/* Filters */}
        <div className="flex items-center gap-2">
          {FILTERS.map(f => (
            <button
              key={f || 'all'}
              onClick={() => setStatusFilter(f)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                statusFilter === f
                  ? 'bg-indigo-600 dark:bg-indigo-500 text-white'
                  : 'bg-white dark:bg-[#161b27] text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-[#1e2535] hover:border-slate-300 dark:hover:border-[#2a3347]'
              }`}
            >
              {f || 'All'}
            </button>
          ))}
          <button
            onClick={() => refetch()}
            className="ml-auto p-2 hover:bg-white dark:hover:bg-[#161b27] rounded-lg border border-transparent hover:border-slate-200 dark:hover:border-[#1e2535] transition-all"
          >
            <RefreshCw className="w-4 h-4 text-slate-400 dark:text-slate-500" />
          </button>
        </div>

        {/* Grid */}
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-6 h-6 animate-spin text-indigo-500" />
          </div>
        ) : experiments.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="w-16 h-16 rounded-2xl bg-indigo-50 dark:bg-indigo-500/10 flex items-center justify-center mb-4">
              <FlaskConical className="w-7 h-7 text-indigo-400 dark:text-indigo-400" />
            </div>
            <h3 className="font-semibold text-slate-700 dark:text-slate-300 mb-1">No experiments yet</h3>
            <p className="text-sm text-slate-400 dark:text-slate-500 mb-5">Create your first A/B test to compare models</p>
            <button
              onClick={() => setShowCreate(true)}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 dark:bg-indigo-500 text-white text-sm rounded-xl hover:bg-indigo-700 dark:hover:bg-indigo-400 transition-colors shadow-md shadow-indigo-200 dark:shadow-indigo-500/20"
            >
              <Plus className="w-4 h-4" />
              New Experiment
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {experiments.map(exp => (
              <ExperimentCard
                key={exp.id}
                experiment={exp}
                onClick={() => setSelectedId(exp.id)}
                onDelete={(e) => {
                  e.stopPropagation();
                  if (window.confirm('Delete this experiment?')) deleteExp(exp.id);
                }}
              />
            ))}
          </div>
        )}
      </div>

      {/* Modals */}
      {showCreate && (
        <CreateExperimentModal
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            queryClient.invalidateQueries({ queryKey: ['experiments'] });
            queryClient.invalidateQueries({ queryKey: ['ab-stats'] });
          }}
        />
      )}

      {selectedId && (
        <ExperimentDetailPanel
          experimentId={selectedId}
          onClose={() => setSelectedId(null)}
        />
      )}
    </div>
  );
}

export default ABTestingPage;