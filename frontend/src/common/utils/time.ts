/**
 * Pure time-formatting utilities. No external dependencies.
 */

/**
 * Formats a duration in milliseconds to a human-readable string.
 *
 * @example
 * formatDuration(90000)  // "1m 30s"
 * formatDuration(3661000) // "1h 1m"
 * formatDuration(500)    // "0s"
 */
export function formatDuration(ms: number): string {
    const totalSeconds = Math.floor(ms / 1000);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    if (hours > 0) {
        return `${hours}h ${minutes}m`;
    }
    if (minutes > 0) {
        return `${minutes}m ${seconds}s`;
    }
    return `${seconds}s`;
}

/**
 * Formats an ISO timestamp as a relative age string ("3m ago", "2h ago", "just now").
 *
 * @param iso - ISO 8601 timestamp string.
 * @param now - Optional reference date; defaults to current date if omitted.
 *
 * @example
 * formatAge('2024-01-01T12:00:00Z', new Date('2024-01-01T12:03:00Z')) // "3m ago"
 * formatAge('2024-01-01T10:00:00Z', new Date('2024-01-01T12:00:00Z')) // "2h ago"
 */
export function formatAge(iso: string, now?: Date): string {
    const reference = now ?? new Date();
    const then = new Date(iso);
    const diffMs = reference.getTime() - then.getTime();

    if (diffMs < 0) return 'just now';

    const diffSeconds = Math.floor(diffMs / 1000);
    if (diffSeconds < 60) return 'just now';

    const diffMinutes = Math.floor(diffSeconds / 60);
    if (diffMinutes < 60) return `${diffMinutes}m ago`;

    const diffHours = Math.floor(diffMinutes / 60);
    if (diffHours < 24) return `${diffHours}h ago`;

    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
}
