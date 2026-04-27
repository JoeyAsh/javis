import type { DeviceEvent } from '../../types';

/**
 * Returns the start of today (midnight local time) as a Unix epoch millisecond timestamp.
 */
export function todayStartMs(): number {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d.getTime();
}

/**
 * Formats an ISO 8601 timestamp as a relative time string (e.g. "2m ago", "just now").
 */
export function relativeTime(iso: string): string {
    const diffMs = Date.now() - new Date(iso).getTime();
    const diffSec = Math.floor(diffMs / 1000);
    if (diffSec < 10) return 'just now';
    if (diffSec < 60) return `${diffSec}s ago`;
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr}h ago`;
    const diffDay = Math.floor(diffHr / 24);
    return `${diffDay}d ago`;
}

/**
 * Group events by correlation_id for display. Events with null correlation_id
 * are each their own singleton group (keyed by id).
 */
export function groupEventsByCorrelation(
    events: DeviceEvent[],
): Array<{ key: string; correlationId: string | null; events: DeviceEvent[] }> {
    const grouped = new Map<string, { correlationId: string | null; events: DeviceEvent[] }>();

    for (const event of events) {
        if (event.correlation_id !== null) {
            const existing = grouped.get(event.correlation_id);
            if (existing) {
                existing.events.push(event);
            } else {
                grouped.set(event.correlation_id, {
                    correlationId: event.correlation_id,
                    events: [event],
                });
            }
        } else {
            // Null correlation_id — each event renders flat with its own group key.
            const key = `single-${event.id.toString()}`;
            grouped.set(key, { correlationId: null, events: [event] });
        }
    }

    return Array.from(grouped.entries()).map(([key, value]) => ({ key, ...value }));
}

/**
 * Truncate a payload preview to a readable one-line string.
 */
export function payloadPreview(payload: Record<string, unknown>): string {
    const keys = Object.keys(payload);
    if (keys.length === 0) return '{}';
    const parts = keys.slice(0, 3).map((k) => {
        const v = payload[k];
        const val = typeof v === 'string' ? v : JSON.stringify(v);
        return `${k}: ${val}`;
    });
    return keys.length > 3 ? `${parts.join(' · ')} …` : parts.join(' · ');
}
