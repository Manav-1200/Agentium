// src/utils/channelHealth.ts
// ─────────────────────────────────────────────────────────────────────────────
// Single source of truth for health-status → Tailwind class mappings.
// Previously this switch statement was duplicated in ChannelMetricsSection
// (ChannelsPage.tsx), MonitoringPage, and any other component that colour-codes
// channel health.  Centralising it here means a single edit propagates everywhere.
// ─────────────────────────────────────────────────────────────────────────────

import type { ChannelHealthStatus } from '@/types';

export interface HealthBadgeProps {
    /** Background colour for badge / card highlight */
    bg: string;
    /** Border colour */
    border: string;
    /** Text colour */
    text: string;
    /** Small indicator dot colour */
    indicator: string;
}

const HEALTH_COLORS: Record<ChannelHealthStatus, HealthBadgeProps> = {
    healthy: {
        bg:        'bg-green-50 dark:bg-green-500/10',
        border:    'border-green-200 dark:border-green-500/20',
        text:      'text-green-700 dark:text-green-400',
        indicator: 'bg-green-500',
    },
    warning: {
        bg:        'bg-yellow-50 dark:bg-yellow-500/10',
        border:    'border-yellow-200 dark:border-yellow-500/20',
        text:      'text-yellow-700 dark:text-yellow-400',
        indicator: 'bg-yellow-500',
    },
    critical: {
        bg:        'bg-red-50 dark:bg-red-500/10',
        border:    'border-red-200 dark:border-red-500/20',
        text:      'text-red-700 dark:text-red-400',
        indicator: 'bg-red-500',
    },
};

/**
 * Returns Tailwind class strings for rendering a health-status badge,
 * indicator dot, card border, and card background.
 *
 * @example
 * const { bg, border, text, indicator } = getHealthBadgeProps(health_status);
 */
export function getHealthBadgeProps(status: ChannelHealthStatus): HealthBadgeProps {
    return HEALTH_COLORS[status] ?? HEALTH_COLORS.healthy;
}

/** Circuit-breaker state → Tailwind classes for the inline badge. */
export function getCircuitBreakerClasses(state: 'closed' | 'half_open' | 'open'): string {
    switch (state) {
        case 'closed':
            return 'bg-green-100 text-green-700 dark:bg-green-500/10 dark:text-green-400 border-green-200 dark:border-green-500/20';
        case 'half_open':
            return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-500/10 dark:text-yellow-400 border-yellow-200 dark:border-yellow-500/20';
        case 'open':
            return 'bg-red-100 text-red-700 dark:bg-red-500/10 dark:text-red-400 border-red-200 dark:border-red-500/20 animate-pulse';
        default:
            return 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300 border-gray-200';
    }
}