/**
 * GitLabPanel — Vitest + RTL tests.
 *
 * Dispatches gitlabStateReceived directly (bypassing RTK Query async
 * onCacheEntryAdded) for deterministic, fast tests.
 */
import { act, screen } from '@testing-library/react';
import { describe, expect, it, beforeEach, vi } from 'vitest';
import { installMockWsClient, _mockWsClientImpl } from '@test/mockWsClient';
import { renderWithProviders } from '@test/renderWithProviders';

vi.mock('@core/websocket/wsClient', () => ({ wsClient: _mockWsClientImpl }));
import gitlabReducer, { gitlabStateReceived } from '../../../gitlabSlice';
import { GitLabPanel } from '../GitLabPanel';
import type { GitLabStatePayload } from '../../../types';

const ws = installMockWsClient();

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

beforeEach(() => {
    ws.reset();
});

describe('GitLabPanel compact mode', () => {
    it('shows loading state when no data received yet', () => {
        renderWithProviders(<GitLabPanel mode="compact" />, {
            reducers: { gitlab: gitlabReducer },
        });
        expect(screen.getByText(/Loading GitLab/i)).toBeTruthy();
    });

    it('renders MR count from live data', () => {
        const { store } = renderWithProviders(<GitLabPanel mode="compact" />, {
            reducers: { gitlab: gitlabReducer },
        });
        act(() => {
            store.dispatch(gitlabStateReceived(livePayload));
        });
        expect(screen.getByText('2')).toBeTruthy();
        expect(screen.getByText('MRs')).toBeTruthy();
    });

    it('renders Issue count from live data', () => {
        const { store } = renderWithProviders(<GitLabPanel mode="compact" />, {
            reducers: { gitlab: gitlabReducer },
        });
        act(() => {
            store.dispatch(gitlabStateReceived(livePayload));
        });
        expect(screen.getByText('1')).toBeTruthy();
        expect(screen.getByText('Issues')).toBeTruthy();
    });

    it('renders first pipeline status in compact mode', () => {
        const { store } = renderWithProviders(<GitLabPanel mode="compact" />, {
            reducers: { gitlab: gitlabReducer },
        });
        act(() => {
            store.dispatch(gitlabStateReceived(livePayload));
        });
        expect(screen.getByText('success')).toBeTruthy();
    });

    it('renders "—" when no pipelines configured', () => {
        const { store } = renderWithProviders(<GitLabPanel mode="compact" />, {
            reducers: { gitlab: gitlabReducer },
        });
        act(() => {
            store.dispatch(gitlabStateReceived({ ...livePayload, pipelines: [] }));
        });
        expect(screen.getByText('—')).toBeTruthy();
    });

    it('shows error badge when data has error and empty lists', () => {
        const { store } = renderWithProviders(<GitLabPanel mode="compact" />, {
            reducers: { gitlab: gitlabReducer },
        });
        act(() => {
            store.dispatch(gitlabStateReceived(errorPayload));
        });
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
        const { store } = renderWithProviders(<GitLabPanel mode="compact" />, {
            reducers: { gitlab: gitlabReducer },
        });
        act(() => {
            store.dispatch(gitlabStateReceived(bigPayload));
        });
        expect(screen.getByText('50+')).toBeTruthy();
    });
});

describe('GitLabPanel expanded mode', () => {
    it('shows waiting message when no data received', () => {
        renderWithProviders(<GitLabPanel mode="expanded" />, {
            reducers: { gitlab: gitlabReducer },
        });
        expect(screen.getByText(/Waiting for GitLab data/i)).toBeTruthy();
    });

    it('renders pipeline project name in expanded mode', () => {
        const { store } = renderWithProviders(<GitLabPanel mode="expanded" />, {
            reducers: { gitlab: gitlabReducer },
        });
        act(() => {
            store.dispatch(gitlabStateReceived(livePayload));
        });
        expect(screen.getByText('project')).toBeTruthy();
    });

    it('renders pipeline status pill in expanded mode', () => {
        const { store } = renderWithProviders(<GitLabPanel mode="expanded" />, {
            reducers: { gitlab: gitlabReducer },
        });
        act(() => {
            store.dispatch(gitlabStateReceived(livePayload));
        });
        expect(screen.getByText('passed')).toBeTruthy();
    });

    it('shows error banner when data.error is set', () => {
        const { store } = renderWithProviders(<GitLabPanel mode="expanded" />, {
            reducers: { gitlab: gitlabReducer },
        });
        act(() => {
            store.dispatch(gitlabStateReceived({ ...livePayload, error: 'Connection refused' }));
        });
        expect(screen.getByText('Connection refused')).toBeTruthy();
    });

    it('shows "No pipelines configured" when pipelines is empty', () => {
        const { store } = renderWithProviders(<GitLabPanel mode="expanded" />, {
            reducers: { gitlab: gitlabReducer },
        });
        act(() => {
            store.dispatch(gitlabStateReceived({ ...livePayload, pipelines: [] }));
        });
        expect(screen.getByText('No pipelines configured')).toBeTruthy();
    });

    it('renders at most 3 pipeline rows', () => {
        const manyPipelines: GitLabStatePayload = {
            ...livePayload,
            pipelines: Array.from({ length: 5 }, (_, i) => ({
                project: `group/project-${i}`,
                status: 'success' as const,
                web_url: '',
                created_at: '2024-01-15T11:00:00Z',
            })),
        };
        const { store } = renderWithProviders(<GitLabPanel mode="expanded" />, {
            reducers: { gitlab: gitlabReducer },
        });
        act(() => {
            store.dispatch(gitlabStateReceived(manyPipelines));
        });
        const rows = screen.getAllByText(/project-[0-4]/);
        expect(rows.length).toBeLessThanOrEqual(3);
    });
});
