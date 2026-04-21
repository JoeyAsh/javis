/**
 * GitLabPanel — Vitest + RTL tests.
 *
 * Tests:
 * 1.  Compact: loading state shows "Loading GitLab…".
 * 2.  Compact: MR count renders from live data.
 * 3.  Compact: Issue count renders from live data.
 * 4.  Compact: first pipeline status dot is present.
 * 5.  Compact: shows "—" when no pipeline configured.
 * 6.  Compact: error badge shown when data has error and empty lists.
 * 7.  Compact: "50+" shown when MR count is at limit.
 * 8.  Expanded: loading state shows waiting message.
 * 9.  Expanded: MR titles render in expanded mode.
 * 10. Expanded: Issue titles render in expanded mode.
 * 11. Expanded: Pipeline project and status render.
 * 12. Expanded: error banner shown when data.error is set.
 * 13. Expanded: "No open MRs" message when mrs is empty.
 * 14. Expanded: "No assigned issues" message when issues is empty.
 */
import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// ---------------------------------------------------------------------------
// Mock the useGitlabState hook
// ---------------------------------------------------------------------------

vi.mock('../../../hooks/useGitlabState', () => ({
  useGitlabState: vi.fn(() => ({
    data: null,
    loading: true,
  })),
}));

import { useGitlabState } from '../../../hooks/useGitlabState';
import { GitLabPanel } from '../GitLab';
import type { GitLabStatePayload } from '../../../types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockUseGitlabState = vi.mocked(useGitlabState);

function setData(payload: GitLabStatePayload | null): void {
  mockUseGitlabState.mockReturnValue({ data: payload, loading: payload === null });
}

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
    {
      id: 2,
      iid: 11,
      title: 'Fix memory leak',
      source_branch: 'fix/memory',
      web_url: 'https://gitlab.com/group/project/-/merge_requests/11',
      author: 'bob',
      created_at: '2024-01-14T08:00:00Z',
      draft: true,
    },
  ],
  issues: [
    {
      id: 42,
      iid: 42,
      title: 'Bug in login form',
      labels: ['bug', 'p1'],
      web_url: 'https://gitlab.com/group/project/-/issues/42',
      author: 'alice',
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
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  mockUseGitlabState.mockReturnValue({ data: null, loading: true });
});

afterEach(() => {
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Compact mode tests
// ---------------------------------------------------------------------------

describe('GitLabPanel compact mode', () => {
  it('shows loading state when data is null', () => {
    render(<GitLabPanel mode="compact" />);
    expect(screen.getByText(/Loading GitLab/i)).toBeTruthy();
  });

  it('renders MR count from live data', () => {
    setData(livePayload);
    render(<GitLabPanel mode="compact" />);
    // Should show "2" for 2 MRs
    expect(screen.getByText('2')).toBeTruthy();
    expect(screen.getByText('MRs')).toBeTruthy();
  });

  it('renders Issue count from live data', () => {
    setData(livePayload);
    render(<GitLabPanel mode="compact" />);
    expect(screen.getByText('1')).toBeTruthy();
    expect(screen.getByText('Issues')).toBeTruthy();
  });

  it('renders first pipeline status in compact mode', () => {
    setData(livePayload);
    render(<GitLabPanel mode="compact" />);
    expect(screen.getByText('success')).toBeTruthy();
  });

  it('renders "—" when no pipelines configured', () => {
    setData({ ...livePayload, pipelines: [] });
    render(<GitLabPanel mode="compact" />);
    expect(screen.getByText('—')).toBeTruthy();
  });

  it('shows error badge when data has error and empty lists', () => {
    setData(errorPayload);
    render(<GitLabPanel mode="compact" />);
    expect(screen.getByText(/GitLab error/i)).toBeTruthy();
  });

  it('shows 50+ when MR count is at the limit', () => {
    const bigPayload: GitLabStatePayload = {
      ...livePayload,
      mrs: Array.from({ length: 50 }, (_, i) => ({
        id: i,
        iid: i,
        title: `MR #${i}`,
        source_branch: `branch-${i}`,
        web_url: '',
        author: 'alice',
        created_at: '2024-01-15T10:00:00Z',
        draft: false,
      })),
    };
    setData(bigPayload);
    render(<GitLabPanel mode="compact" />);
    expect(screen.getByText('50+')).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// Expanded mode tests
// ---------------------------------------------------------------------------

describe('GitLabPanel expanded mode', () => {
  it('shows waiting message when data is null', () => {
    render(<GitLabPanel mode="expanded" />);
    expect(screen.getByText(/Waiting for GitLab data/i)).toBeTruthy();
  });

  it('renders MR titles in expanded mode', () => {
    setData(livePayload);
    render(<GitLabPanel mode="expanded" />);
    expect(screen.getByText('Add dark mode')).toBeTruthy();
    expect(screen.getByText('Fix memory leak')).toBeTruthy();
  });

  it('renders issue titles in expanded mode', () => {
    setData(livePayload);
    render(<GitLabPanel mode="expanded" />);
    expect(screen.getByText('Bug in login form')).toBeTruthy();
  });

  it('renders pipeline project and status in expanded mode', () => {
    setData(livePayload);
    render(<GitLabPanel mode="expanded" />);
    expect(screen.getByText('group/project')).toBeTruthy();
    // success appears in both compact (first pipeline dot) and pipeline list
    expect(screen.getAllByText('success').length).toBeGreaterThanOrEqual(1);
  });

  it('shows error banner when data.error is set', () => {
    setData({ ...livePayload, error: 'Connection refused' });
    render(<GitLabPanel mode="expanded" />);
    expect(screen.getByText('Connection refused')).toBeTruthy();
  });

  it('shows "No open MRs" when mrs is empty', () => {
    setData({ ...livePayload, mrs: [] });
    render(<GitLabPanel mode="expanded" />);
    expect(screen.getByText('No open MRs')).toBeTruthy();
  });

  it('shows "No assigned issues" when issues is empty', () => {
    setData({ ...livePayload, issues: [] });
    render(<GitLabPanel mode="expanded" />);
    expect(screen.getByText('No assigned issues')).toBeTruthy();
  });
});
