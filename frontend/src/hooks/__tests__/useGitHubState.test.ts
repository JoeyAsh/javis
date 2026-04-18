/**
 * Tests for the useGitHubState hook.
 *
 * Strategy: mock subscribeGitHubStateStream at the module level so no real
 * WebSocket is needed. Tests fire the captured listener directly to simulate
 * incoming WS frames.
 */
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { GitHubStateListener } from '../useWebSocket';

// Captured listener injected by the mock subscription.
let capturedListener: GitHubStateListener | null = null;

vi.mock('../useWebSocket', () => ({
  subscribeGitHubStateStream: vi.fn((listener: GitHubStateListener) => {
    capturedListener = listener;
    return () => {
      capturedListener = null;
    };
  }),
}));

import { useGitHubState } from '../useGitHubState';
import type { GitHubStatePayload } from '../../types';

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

const livePayload: GitHubStatePayload = {
  prs: [
    {
      id: '1',
      repo: 'owner/repo',
      title: 'Fix critical bug',
      author: 'alice',
      html_url: 'https://github.com/owner/repo/pull/1',
      updated_at: '2024-01-15T10:00:00Z',
    },
  ],
  issues: [
    {
      id: '42',
      repo: 'owner/repo',
      title: 'Open issue',
      html_url: 'https://github.com/owner/repo/issues/42',
      updated_at: '2024-01-14T08:00:00Z',
    },
  ],
  ci: [
    {
      repo: 'owner/repo',
      status: 'success',
      ran_at: '2024-01-15T11:00:00Z',
      html_url: 'https://github.com/owner/repo/actions/runs/999',
    },
  ],
  fetched_at: '2024-01-15T12:00:00Z',
  stale: false,
};

const stalePayload: GitHubStatePayload = {
  ...livePayload,
  stale: true,
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useGitHubState', () => {
  beforeEach(() => {
    capturedListener = null;
  });

  afterEach(() => {
    capturedListener = null;
    vi.clearAllMocks();
  });

  it('returns loading=true and data=null before first message', () => {
    const { result } = renderHook(() => useGitHubState());
    expect(result.current.loading).toBe(true);
    expect(result.current.data).toBeNull();
  });

  it('populates data and sets loading=false on first WS frame', async () => {
    const { result } = renderHook(() => useGitHubState());

    expect(result.current.loading).toBe(true);

    act(() => {
      capturedListener?.(livePayload);
    });

    expect(result.current.loading).toBe(false);
    expect(result.current.data).not.toBeNull();
    expect(result.current.data?.prs[0].title).toBe('Fix critical bug');
  });

  it('exposes PR data correctly', async () => {
    const { result } = renderHook(() => useGitHubState());

    act(() => {
      capturedListener?.(livePayload);
    });

    const prs = result.current.data?.prs ?? [];
    expect(prs).toHaveLength(1);
    expect(prs[0].id).toBe('1');
    expect(prs[0].repo).toBe('owner/repo');
    expect(prs[0].author).toBe('alice');
  });

  it('exposes issue data correctly', async () => {
    const { result } = renderHook(() => useGitHubState());

    act(() => {
      capturedListener?.(livePayload);
    });

    const issues = result.current.data?.issues ?? [];
    expect(issues).toHaveLength(1);
    expect(issues[0].id).toBe('42');
  });

  it('exposes CI data correctly', async () => {
    const { result } = renderHook(() => useGitHubState());

    act(() => {
      capturedListener?.(livePayload);
    });

    const ci = result.current.data?.ci ?? [];
    expect(ci).toHaveLength(1);
    expect(ci[0].status).toBe('success');
    expect(ci[0].repo).toBe('owner/repo');
  });

  it('updates data on subsequent WS frames', async () => {
    const { result } = renderHook(() => useGitHubState());

    act(() => {
      capturedListener?.(livePayload);
    });
    expect(result.current.data?.stale).toBe(false);

    act(() => {
      capturedListener?.(stalePayload);
    });
    expect(result.current.data?.stale).toBe(true);
  });

  it('reflects stale=true when payload marks data stale', async () => {
    const { result } = renderHook(() => useGitHubState());

    act(() => {
      capturedListener?.(stalePayload);
    });

    expect(result.current.data?.stale).toBe(true);
    expect(result.current.loading).toBe(false);
  });

  it('unsubscribes on unmount', () => {
    const { unmount } = renderHook(() => useGitHubState());
    expect(capturedListener).not.toBeNull();

    unmount();
    expect(capturedListener).toBeNull();
  });
});
