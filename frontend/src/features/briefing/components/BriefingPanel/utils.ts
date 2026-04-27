/**
 * Utility helpers for BriefingPanel — time formatting only.
 * Kept here so the .tsx stays free of top-level non-component functions.
 */

/**
 * Formats an ISO date string as HH:MM in the local timezone.
 */
export function formatLocalTime(iso: string): string {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
}

/**
 * Returns a human-readable relative time string from an ISO date to now.
 * E.g. "vor 3 Minuten" (de) or "3 minutes ago" (en).
 */
export function formatRelativeTime(iso: string, language: 'de' | 'en'): string {
    const diffMs = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diffMs / 60_000);
    const hours = Math.floor(diffMs / 3_600_000);

    if (language === 'de') {
        if (mins < 1) return 'gerade eben';
        if (mins < 60) return `vor ${mins} Minute${mins === 1 ? '' : 'n'}`;
        return `vor ${hours} Stunde${hours === 1 ? '' : 'n'}`;
    }

    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins} minute${mins === 1 ? '' : 's'} ago`;
    return `${hours} hour${hours === 1 ? '' : 's'} ago`;
}
