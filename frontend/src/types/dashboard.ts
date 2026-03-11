// ─── Dashboard-specific Types ──────────────────────────────────────────────
// Dedicated shapes for the dashboard layer.
// Re-exported from types/index.ts so consumers can import from either path.

import type { Agent, Task } from './index';

/** Pre-computed aggregate counters shown in the stats grid. */
export interface DashboardStats {
    totalAgents:     number;
    activeAgents:    number;
    pendingTasks:    number;
    completedTasks:  number;
    failedTasks:     number;
    inProgressTasks: number;
    /** 0–100 integer — completedTasks / nonPending × 100 */
    successRate:     number;
    lastRefreshedAt: Date | null;
}

/** Lightweight agent row used in the AgentsList widget. */
export type AgentSummary = Pick<
    Agent,
    'id' | 'name' | 'status' | 'agent_type' | 'current_task_title' | 'health_score'
>;

/** Lightweight task row used in the RecentTasks widget. */
export type TaskSummary = Pick<
    Task,
    'id' | 'title' | 'status' | 'priority' | 'progress' | 'updated_at' | 'created_at'
>;

/** Shape returned by GET /api/v1/dashboard/summary */
export interface DashboardSummaryResponse {
    agents: {
        total:     number;
        active:    number;
        working:   number;
        suspended: number;
    };
    tasks: {
        total:       number;
        pending:     number;
        in_progress: number;
        completed:   number;
        failed:      number;
    };
    recent_tasks:  TaskSummary[];
    active_agents: AgentSummary[];
    generated_at:  string;
}