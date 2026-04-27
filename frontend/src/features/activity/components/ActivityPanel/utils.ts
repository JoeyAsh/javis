import type { NarrationSeverity, SourceStatus } from '../../types';

/**
 * Returns Tailwind class names for a severity badge.
 * Used by ActivityHistoryList for colour-coded item badges.
 */
export function severityBadgeClasses(severity: NarrationSeverity): string {
    switch (severity) {
        case 'info':
            return 'bg-blue-900/40 text-blue-300 border border-blue-700/50';
        case 'update':
            return 'bg-cyan-900/40 text-cyan-300 border border-cyan-700/50';
        case 'urgent':
            return 'bg-red-900/40 text-red-400 border border-red-700/50';
        case 'completion':
            return 'bg-green-900/40 text-green-300 border border-green-700/50';
    }
}

/**
 * Returns Tailwind class names for a source-status badge.
 */
export function statusBadgeClasses(status: SourceStatus): string {
    switch (status) {
        case 'starting':
            return 'bg-slate-800/50 text-slate-300 border border-slate-600/50';
        case 'in_progress':
            return 'bg-cyan-900/40 text-cyan-300 border border-cyan-700/50';
        case 'done':
            return 'bg-green-900/40 text-green-300 border border-green-700/50';
        case 'blocked':
            return 'bg-red-900/40 text-red-400 border border-red-700/50';
    }
}

/**
 * Formats an ISO 8601 timestamp as a relative time string (e.g. "2m ago", "just now").
 * Designed for display in the activity history list.
 */
export function relativeTime(iso: string): string {
    const diffMs = Date.now() - new Date(iso).getTime();
    const diffSec = Math.floor(diffMs / 1000);
    if (diffSec < 10) return 'just now';
    if (diffSec < 60) return `${diffSec}s ago`;
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHr = Math.floor(diffMin / 60);
    return `${diffHr}h ago`;
}

/**
 * Formats an ISO 8601 quiet-until timestamp as "HH:MM" (local time).
 */
export function formatQuietUntilTime(iso: string): string {
    const d = new Date(iso);
    const h = d.getHours().toString().padStart(2, '0');
    const m = d.getMinutes().toString().padStart(2, '0');
    return `${h}:${m}`;
}
