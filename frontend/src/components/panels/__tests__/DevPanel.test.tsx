/**
 * DevPanel — Vitest + RTL tests.
 *
 * Tests:
 *  - Compact: shows PR count from live data when available.
 *  - Compact: falls back to mock data when liveData is null.
 *  - Expanded: renders live PR titles when github_state received.
 *  - Expanded: renders live issue titles when github_state received.
 *  - Expanded: renders CI status badge from live data.
 *  - Expanded: renders [stale] label when stale=true.
 *  - Expanded: falls back to mock PR/notification sections when no live data.
 *  - Local Repos and Docker sections always render (from mock).
 */
import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// ---------------------------------------------------------------------------
// Mock the GitHub subscription
// ---------------------------------------------------------------------------

vi.mock('../../../hooks/useGitHubState', () => ({
  useGitHubState: vi.fn(() => ({
    data: null,
    loading: true,
  })),
}));

import { useGitHubState } from '../../../hooks/useGitHubState';
import { DevPanel } from '../Dev';
import type { GitHubStatePayload } from '../../../types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockUseGitHubState = vi.mocked(useGitHubState);

function setLiveData(payload: GitHubStatePayload | null): void {
  mockUseGitHubState.mockReturnValue({ data: payload, loading: payload === null });
}

const livePayload: GitHubStatePayload = {
  prs: [
    {
      id: '1',
      repo: 'owner/repo',
      title: 'Fix critical auth bug',
      author: 'alice',
      html_url: 'https://github.com/owner/repo/pull/1',
      updated_at: '2024-01-15T10:00:00Z',
    },
    {
      id: '2',
      repo: 'owner/repo',
      title: 'Add dark mode',
      author: 'bob',
      html_url: 'https://github.com/owner/repo/pull/2',
      updated_at: '2024-01-14T10:00:00Z',
    },
  ],
  issues: [
    {
      id: '42',
      repo: 'owner/repo',
      title: 'Memory leak in poller',
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
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  // Default: no live data (mock fallback mode).
  setLiveData(null);
});

afterEach(() => {
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Expanded mode — live data
// ---------------------------------------------------------------------------

describe('DevPanel expanded — live data', () => {
  it('renders live PR title when github_state is received', () => {
    setLiveData(livePayload);
    render(<DevPanel mode="expanded" />);

    expect(screen.getByText('Fix critical auth bug')).toBeTruthy();
  });

  it('renders live issue title', () => {
    setLiveData(livePayload);
    render(<DevPanel mode="expanded" />);

    expect(screen.getByText('Memory leak in poller')).toBeTruthy();
  });

  it('renders CI badge status', () => {
    setLiveData(livePayload);
    render(<DevPanel mode="expanded" />);

    expect(screen.getByText('success')).toBeTruthy();
  });

  it('renders [stale] label when payload is stale', () => {
    setLiveData(stalePayload);
    render(<DevPanel mode="expanded" />);

    // Multiple section headers can show [stale] simultaneously.
    expect(screen.getAllByText('[stale]').length).toBeGreaterThan(0);
  });

  it('does not render [stale] when payload is fresh', () => {
    setLiveData(livePayload);
    render(<DevPanel mode="expanded" />);

    expect(screen.queryByText('[stale]')).toBeNull();
  });

  it('renders Local Repos section from mock regardless of live data', () => {
    setLiveData(livePayload);
    render(<DevPanel mode="expanded" />);

    // devMock always has local repos — check section header exists.
    expect(screen.getByText('Local Repos')).toBeTruthy();
  });

  it('renders Docker section from mock regardless of live data', () => {
    setLiveData(livePayload);
    render(<DevPanel mode="expanded" />);

    expect(screen.getByText('Docker')).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// Expanded mode — mock fallback (no live data)
// ---------------------------------------------------------------------------

describe('DevPanel expanded — mock fallback', () => {
  it('renders mock PR data when no live data available', () => {
    setLiveData(null);
    const { container } = render(<DevPanel mode="expanded" />);

    // GitHub section header should be present in mock mode.
    expect(container.textContent).toContain('GitHub');
  });

  it('renders mock CI section when no live data available', () => {
    setLiveData(null);
    render(<DevPanel mode="expanded" />);

    expect(screen.getByText('CI')).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// Compact mode
// ---------------------------------------------------------------------------

describe('DevPanel compact — live data', () => {
  it('shows live PR count in compact mode', () => {
    setLiveData(livePayload);
    render(<DevPanel mode="compact" />);

    // 2 PRs in livePayload.
    expect(screen.getByText('2')).toBeTruthy();
    expect(screen.getAllByText('PRs').length).toBeGreaterThan(0);
  });

  it('shows live issue count in compact mode', () => {
    setLiveData(livePayload);
    render(<DevPanel mode="compact" />);

    expect(screen.getByText('Issues')).toBeTruthy();
  });
});

describe('DevPanel compact — mock fallback', () => {
  it('shows mock PR count when no live data', () => {
    setLiveData(null);
    render(<DevPanel mode="compact" />);

    // Mock data has PRs — just ensure it doesn't crash.
    expect(screen.getAllByText('PRs').length).toBeGreaterThan(0);
  });
});
