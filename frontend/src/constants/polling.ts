// ─── Polling & Stale-Time Constants ──────────────────────────────────────────
// One place to tune every refetchInterval / staleTime value.
// Import these into any useQuery call instead of hard-coding numbers inline.

/** Background re-fetch intervals (milliseconds). */
export const POLL_INTERVALS = {
    /** Agent list — changes when agents are spawned or change status. */
    AGENTS:    30_000,
    /** Task list — changes more frequently during active execution. */
    TASKS:     20_000,
    /** Channel list — rarely changes once configured. */
    CHANNELS:  45_000,
    /** Per-channel health / circuit-breaker state. */
    METRICS:   10_000,
    /** Dashboard aggregate summary (if using the /dashboard/summary endpoint). */
    DASHBOARD: 30_000,
} as const;

/**
 * Data is considered "fresh" for this many milliseconds.
 * Prevents redundant re-fetches on window-focus or component remounts
 * when the data was recently loaded.
 */
export const STALE_TIMES = {
    AGENTS:    15_000,
    TASKS:     10_000,
    CHANNELS:  30_000,
    METRICS:    8_000,
    DASHBOARD: 15_000,
} as const;