/**
 * SelfFix feature mock data (moved from src/mock/selfFixMock.ts).
 */
import type { SelfFixEntry } from './types';

export const selfFixMock: SelfFixEntry[] = [
    {
        id: 'sf-1',
        status: 'in_progress',
        summary: 'Analyzing calendar-sync error...',
        detail: 'Stack trace in CalendarAgent.refresh() — investigating OAuth token refresh race.',
        startedAt: new Date(Date.now() - 90_000).toISOString(),
    },
    {
        id: 'sf-2',
        status: 'completed',
        summary: 'Fixed: wake-word false positives on low-SNR mic',
        detail: 'Adjusted picovoice sensitivity 0.62 → 0.48 and added RMS floor guard.',
        commitSha: 'a3f12ce',
        added: 12,
        removed: 4,
        startedAt: new Date(Date.now() - 22 * 60_000).toISOString(),
    },
];
