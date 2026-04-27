/**
 * Sample data for development / Storybook.
 */
import type { NarrationItem, SourceEntry } from './types';
import type { ActivityState } from './activitySlice';

export const MOCK_NARRATION_ITEMS: NarrationItem[] = [
    {
        id: '1',
        text: 'Backend implementation complete — migrating to frontend next.',
        severity: 'completion',
        source: 'claude-code-91',
        created_at: new Date(Date.now() - 2 * 60_000).toISOString(),
        ttl_seconds: null,
    },
    {
        id: '2',
        text: 'Running tests — 3 failures in auth module.',
        severity: 'urgent',
        source: 'claude-code-91',
        created_at: new Date(Date.now() - 5 * 60_000).toISOString(),
        ttl_seconds: null,
    },
    {
        id: '3',
        text: 'Morning briefing scheduled for 08:00.',
        severity: 'info',
        source: 'morning-briefing',
        created_at: new Date(Date.now() - 10 * 60_000).toISOString(),
        ttl_seconds: 3600,
    },
    {
        id: '4',
        text: 'Spotify token refreshed successfully.',
        severity: 'update',
        source: 'spotify',
        created_at: new Date(Date.now() - 15 * 60_000).toISOString(),
        ttl_seconds: null,
    },
];

export const MOCK_SOURCES: Record<string, SourceEntry> = {
    'claude-code-91': {
        status: 'in_progress',
        message: 'Backend done, frontend next',
        updated_at: new Date(Date.now() - 2 * 60_000).toISOString(),
    },
    'morning-briefing': {
        status: 'done',
        message: 'Briefing delivered',
        updated_at: new Date(Date.now() - 10 * 60_000).toISOString(),
    },
};

export const MOCK_ACTIVITY_STATE: ActivityState = {
    state: 'active_dialogue',
    quietUntil: null,
    sources: MOCK_SOURCES,
    history: MOCK_NARRATION_ITEMS,
    hasLiveData: true,
};
