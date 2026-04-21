/**
 * Tests for the useGitlabState hook.
 *
 * Strategy: mock subscribeGitLabStateStream at the module level so no real
 * WebSocket is needed. Tests fire the captured listener directly to simulate
 * incoming WS frames.
 *
 * Test plan:
 * 1. Returns loading=true and data=null before first message.
 * 2. Populates data and sets loading=false on first WS frame.
 * 3. Exposes MR data correctly.
 * 4. Exposes issue data correctly.
 * 5. Exposes pipeline data correctly.
 * 6. Updates data on subsequent WS frames.
 * 7. Sets error field when payload has error.
 * 8. Unsubscribes on unmount.
 */
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { GitLabStateListener } from '../useWebSocket';

// Captured listener injected by the mock subscription.
let capturedListener: GitLabStateListener | null = null;

vi.mock('../useWebSocket', () => ({
    subscribeGitLabStateStream: vi.fn((listener: GitLabStateListener) => {
        capturedListener = listener;
        return () => {
            capturedListener = null;
        };
    }),
}));

import { useGitlabState } from '../useGitlabState';
import type { GitLabStatePayload } from '../../types';

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

const livePayload: GitLabStatePayload = {
    mrs: [
        {
            id: 1,
            iid: 10,
            title: 'Add dark mode',
            source_branch: 'feature/dark-mode',
            web_url: 'https://gitlab.com/group/project/-/merge_requests/10',
            author: 'alice',
            created_at: '2024-01-15T10:00:00Z',
            draft: false,
        },
    ],
    issues: [
        {
            id: 42,
            iid: 42,
            title: 'Bug in login',
            labels: ['bug', 'p1'],
            web_url: 'https://gitlab.com/group/project/-/issues/42',
            author: 'bob',
            created_at: '2024-01-14T09:00:00Z',
        },
    ],
    pipelines: [
        {
            project: 'group/project',
            status: 'success',
            web_url: 'https://gitlab.com/group/project/-/pipelines/999',
            created_at: '2024-01-15T11:00:00Z',
        },
    ],
    error: null,
};

const errorPayload: GitLabStatePayload = {
    mrs: [],
    issues: [],
    pipelines: [],
    error: 'Unauthorized — check GITLAB_TOKEN',
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useGitlabState', () => {
    beforeEach(() => {
        capturedListener = null;
    });

    afterEach(() => {
        capturedListener = null;
        vi.clearAllMocks();
    });

    it('returns loading=true and data=null before first message', () => {
        const { result } = renderHook(() => useGitlabState());
        expect(result.current.loading).toBe(true);
        expect(result.current.data).toBeNull();
    });

    it('populates data and sets loading=false on first WS frame', () => {
        const { result } = renderHook(() => useGitlabState());

        expect(result.current.loading).toBe(true);

        act(() => {
            capturedListener?.(livePayload);
        });

        expect(result.current.loading).toBe(false);
        expect(result.current.data).not.toBeNull();
        expect(result.current.data?.mrs[0].title).toBe('Add dark mode');
    });

    it('exposes MR data correctly', () => {
        const { result } = renderHook(() => useGitlabState());

        act(() => {
            capturedListener?.(livePayload);
        });

        const mrs = result.current.data?.mrs ?? [];
        expect(mrs).toHaveLength(1);
        expect(mrs[0].id).toBe(1);
        expect(mrs[0].iid).toBe(10);
        expect(mrs[0].source_branch).toBe('feature/dark-mode');
        expect(mrs[0].author).toBe('alice');
        expect(mrs[0].draft).toBe(false);
    });

    it('exposes issue data correctly', () => {
        const { result } = renderHook(() => useGitlabState());

        act(() => {
            capturedListener?.(livePayload);
        });

        const issues = result.current.data?.issues ?? [];
        expect(issues).toHaveLength(1);
        expect(issues[0].id).toBe(42);
        expect(issues[0].title).toBe('Bug in login');
        expect(issues[0].labels).toEqual(['bug', 'p1']);
    });

    it('exposes pipeline data correctly', () => {
        const { result } = renderHook(() => useGitlabState());

        act(() => {
            capturedListener?.(livePayload);
        });

        const pipelines = result.current.data?.pipelines ?? [];
        expect(pipelines).toHaveLength(1);
        expect(pipelines[0].project).toBe('group/project');
        expect(pipelines[0].status).toBe('success');
    });

    it('updates data on subsequent WS frames', () => {
        const { result } = renderHook(() => useGitlabState());

        act(() => {
            capturedListener?.(livePayload);
        });
        expect(result.current.data?.error).toBeNull();

        act(() => {
            capturedListener?.(errorPayload);
        });
        expect(result.current.data?.error).toBe('Unauthorized — check GITLAB_TOKEN');
    });

    it('exposes error field when payload has error', () => {
        const { result } = renderHook(() => useGitlabState());

        act(() => {
            capturedListener?.(errorPayload);
        });

        expect(result.current.data?.error).toBe('Unauthorized — check GITLAB_TOKEN');
        expect(result.current.data?.mrs).toHaveLength(0);
        expect(result.current.loading).toBe(false);
    });

    it('unsubscribes on unmount', () => {
        const { unmount } = renderHook(() => useGitlabState());
        expect(capturedListener).not.toBeNull();

        unmount();
        expect(capturedListener).toBeNull();
    });
});
