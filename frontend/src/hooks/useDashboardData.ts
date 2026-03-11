// ─── useDashboardData ─────────────────────────────────────────────────────────

import { useMemo }    from 'react';
import { useQuery }   from '@tanstack/react-query';
import { api }        from '@/services/api';
import type { Agent, Task } from '@/types';
import type { DashboardStats } from '@/types/dashboard';
import { POLL_INTERVALS, STALE_TIMES } from '@/constants/polling';

// ── Response normalisers ──────────────────────────────────────────────────────
// The backend may return `{ agents: [...] }` or a bare array depending on
// the endpoint version.  These helpers always produce a typed array.

function toAgentArray(data: unknown): Agent[] {
    if (Array.isArray(data)) return data as Agent[];
    if (data && typeof data === 'object' && 'agents' in data) {
        const d = data as { agents?: unknown };
        if (Array.isArray(d.agents)) return d.agents as Agent[];
    }
    return [];
}

function toTaskArray(data: unknown): Task[] {
    if (Array.isArray(data)) return data as Task[];
    if (data && typeof data === 'object' && 'tasks' in data) {
        const d = data as { tasks?: unknown };
        if (Array.isArray(d.tasks)) return d.tasks as Task[];
    }
    return [];
}

// ── Status constants ──────────────────────────────────────────────────────────

const ACTIVE_AGENT_STATUSES  = new Set(['active', 'working', 'deliberating']);
const PENDING_TASK_STATUSES  = new Set(['pending', 'deliberating']);
/** Sort order for the agents list widget — lower index = shown first. */
const AGENT_STATUS_ORDER: Agent['status'][] = [
    'working', 'active', 'deliberating', 'initializing', 'suspended',
];

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useDashboardData() {
    // ── Agents ────────────────────────────────────────────────────────────────
    const agentsQuery = useQuery<Agent[]>({
        queryKey:             ['agents'],
        queryFn:              async () => toAgentArray((await api.get('/api/v1/agents')).data),
        staleTime:            STALE_TIMES.AGENTS,
        refetchInterval:      POLL_INTERVALS.AGENTS,
        refetchOnWindowFocus: false,
        placeholderData:      [] as Agent[],
    });

    // ── Tasks ─────────────────────────────────────────────────────────────────
    const tasksQuery = useQuery<Task[]>({
        queryKey:             ['tasks'],
        queryFn:              async () => toTaskArray((await api.get('/api/v1/tasks/')).data),
        staleTime:            STALE_TIMES.TASKS,
        refetchInterval:      POLL_INTERVALS.TASKS,
        refetchOnWindowFocus: false,
        placeholderData:      [] as Task[],
    });

    const agents = agentsQuery.data ?? [];
    const tasks  = tasksQuery.data  ?? [];

    // ── Derived stats ─────────────────────────────────────────────────────────
    const stats = useMemo<DashboardStats>(() => {
        const completedTasks  = tasks.filter(t => t.status === 'completed').length;
        const nonPendingCount = tasks.filter(t => !PENDING_TASK_STATUSES.has(t.status)).length;

        return {
            totalAgents:     agents.length,
            activeAgents:    agents.filter(a => ACTIVE_AGENT_STATUSES.has(a.status)).length,
            pendingTasks:    tasks.filter(t => PENDING_TASK_STATUSES.has(t.status)).length,
            completedTasks,
            failedTasks:     tasks.filter(t => t.status === 'failed').length,
            inProgressTasks: tasks.filter(t => t.status === 'in_progress').length,
            successRate:     nonPendingCount > 0
                                 ? Math.round((completedTasks / nonPendingCount) * 100)
                                 : 0,
            lastRefreshedAt: new Date(),
        };
    }, [agents, tasks]);

    // ── Recent tasks (latest 5 by updated_at / created_at) ───────────────────
    const recentTasks = useMemo(
        () =>
            [...tasks]
                .sort((a, b) => {
                    const ta = new Date(a.updated_at ?? a.created_at ?? 0).getTime();
                    const tb = new Date(b.updated_at ?? b.created_at ?? 0).getTime();
                    return tb - ta;
                })
                .slice(0, 5),
        [tasks],
    );

    // ── Active agents list (top 6, sorted by "busyness") ─────────────────────
    const activeAgentsList = useMemo(
        () =>
            [...agents]
                .filter(a => !a.is_terminated && a.status !== 'terminated')
                .sort((a, b) => {
                    const ia = AGENT_STATUS_ORDER.indexOf(a.status);
                    const ib = AGENT_STATUS_ORDER.indexOf(b.status);
                    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
                })
                .slice(0, 6),
        [agents],
    );

    return {
        // ── Raw data ───────────────────────────────────────────────────────
        agents,
        tasks,
        // ── Derived slices ─────────────────────────────────────────────────
        stats,
        recentTasks,
        activeAgentsList,
        // ── Per-domain loading / error flags ───────────────────────────────
        // Kept separate so each widget can degrade independently.
        isAgentsLoading: agentsQuery.isLoading,
        isTasksLoading:  tasksQuery.isLoading,
        isAgentsError:   agentsQuery.isError,
        isTasksError:    tasksQuery.isError,
        // True only while BOTH are on their very first fetch (no cached data yet)
        isLoading:       agentsQuery.isLoading && tasksQuery.isLoading,
        // Retry callbacks wired to WidgetErrorFallback buttons
        refetchAgents:   agentsQuery.refetch,
        refetchTasks:    tasksQuery.refetch,
    };
}