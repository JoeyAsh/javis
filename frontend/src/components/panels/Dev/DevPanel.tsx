/**
 * DevPanel — panel body for the developer toolkit.
 * Returns only body content; the Window wrapper supplies chrome via HudPanel.
 *
 * Shows GitHub PRs, Issues, CI (live when available), Local Repos, Docker.
 * Falls back to mock data when the backend GitHub poller is not running.
 *
 * SFX: click baked into buttons (handled externally by HudButton primitives).
 */
import type { ReactElement } from 'react';
import { devMock } from '../../../mock/devMock';
import type {
    CIStatus,
    DevToolkitMock,
    GithubCIRunLive,
    GithubIssueLive,
    GithubPRLive,
    GitHubStatePayload,
    PanelMode,
    RepoSyncStatus,
} from '../../../types';
import { useGitHubState } from '../../../hooks/useGitHubState';
import './DevPanel.css';

export interface DevPanelProps {
    data?: DevToolkitMock;
    mode?: PanelMode;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function repoPillClass(status: RepoSyncStatus): string {
    switch (status) {
        case 'clean':
            return 'pill ok';
        case 'dirty':
            return 'pill warn';
        case 'behind':
            return 'pill err';
        case 'ahead':
            return 'pill info';
    }
}

function ciPillClass(status: CIStatus): string {
    switch (status) {
        case 'success':
            return 'pill ok';
        case 'failure':
            return 'pill err';
        case 'running':
            return 'pill info';
        case 'pending':
            return 'pill';
    }
}

function relativeTime(iso: string): string {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60_000);
    if (mins < 1) return 'now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
}

// ---------------------------------------------------------------------------
// Section header
// ---------------------------------------------------------------------------

function SectionHeader({
    label,
    right,
    stale,
}: {
    label: string;
    right?: string;
    stale?: boolean;
}): ReactElement {
    return (
        <div className="dev-section">
            <span className="dev-section__label">
                {label}
                {stale && <span className="dev-section__stale">[stale]</span>}
            </span>
            {right !== undefined && <span className="dev-section__right">{right}</span>}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Live GitHub sub-sections
// ---------------------------------------------------------------------------

function LivePRList({ prs, stale }: { prs: GithubPRLive[]; stale: boolean }): ReactElement {
    return (
        <>
            <SectionHeader label="GitHub PRs" right={`${prs.length} open`} stale={stale} />
            {prs.slice(0, 3).map((pr) => (
                <div className="list-item" key={pr.id} style={{ paddingTop: 4, paddingBottom: 4 }}>
                    <div
                        style={{
                            fontSize: 11,
                            color: 'var(--text)',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                        }}
                    >
                        {pr.title}
                    </div>
                    <div
                        style={{
                            fontSize: 9,
                            color: 'var(--text-muted)',
                            display: 'flex',
                            justifyContent: 'space-between',
                        }}
                    >
                        <span>
                            {pr.repo} · {pr.author}
                        </span>
                        <span>{relativeTime(pr.updated_at)}</span>
                    </div>
                </div>
            ))}
            {prs.length === 0 && (
                <div
                    className="list-item"
                    style={{ fontSize: 10, color: 'var(--text-muted)', paddingTop: 4 }}
                >
                    No open PRs
                </div>
            )}
        </>
    );
}

function LiveIssueList({
    issues,
    stale,
}: {
    issues: GithubIssueLive[];
    stale: boolean;
}): ReactElement {
    return (
        <>
            <SectionHeader
                label="GitHub Issues"
                right={`${issues.length} assigned`}
                stale={stale}
            />
            {issues.slice(0, 3).map((issue) => (
                <div
                    className="list-item"
                    key={issue.id}
                    style={{ paddingTop: 4, paddingBottom: 4 }}
                >
                    <div
                        style={{
                            fontSize: 11,
                            color: 'var(--text)',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                        }}
                    >
                        {issue.title}
                    </div>
                    <div
                        style={{
                            fontSize: 9,
                            color: 'var(--text-muted)',
                            display: 'flex',
                            justifyContent: 'space-between',
                        }}
                    >
                        <span>{issue.repo}</span>
                        <span>{relativeTime(issue.updated_at)}</span>
                    </div>
                </div>
            ))}
            {issues.length === 0 && (
                <div
                    className="list-item"
                    style={{ fontSize: 10, color: 'var(--text-muted)', paddingTop: 4 }}
                >
                    No assigned issues
                </div>
            )}
        </>
    );
}

function LiveCIList({ ci, stale }: { ci: GithubCIRunLive[]; stale: boolean }): ReactElement {
    return (
        <>
            <SectionHeader label="CI" stale={stale} />
            {ci.map((run) => (
                <div
                    className="list-item"
                    key={run.repo}
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        paddingTop: 4,
                        paddingBottom: 4,
                    }}
                >
                    <span className={ciPillClass(run.status)}>{run.status}</span>
                    <span style={{ fontSize: 11, color: 'var(--text)', flex: 1 }}>{run.repo}</span>
                    <span className="mono-small">{relativeTime(run.ran_at)}</span>
                </div>
            ))}
            {ci.length === 0 && (
                <div
                    className="list-item"
                    style={{ fontSize: 10, color: 'var(--text-muted)', paddingTop: 4 }}
                >
                    No CI runs
                </div>
            )}
        </>
    );
}

// ---------------------------------------------------------------------------
// Compact view
// ---------------------------------------------------------------------------

function DevCompact({
    data,
    liveData,
}: {
    data: DevToolkitMock;
    liveData: GitHubStatePayload | null;
}): ReactElement {
    const prs = liveData !== null ? liveData.prs.length : data.prs.length;
    const issues = liveData !== null ? liveData.issues.length : 0;
    const dirty = data.repos.filter((r) => r.status === 'dirty' || r.status === 'behind').length;
    const containers = data.docker.filter((c) => c.status === 'running').length;
    const firstPR = liveData !== null ? liveData.prs[0] : data.prs[0];

    return (
        <div className="dev-compact">
            <div className="dev-compact__row">
                <span>
                    <span className="dev-compact__count" style={{ color: 'var(--accent-bright)' }}>
                        {prs}
                    </span>
                    <span className="dev-compact__label">PRs</span>
                </span>
                {liveData !== null ? (
                    <span>
                        <span className="dev-compact__count" style={{ color: 'var(--warning)' }}>
                            {issues}
                        </span>
                        <span className="dev-compact__label">Issues</span>
                    </span>
                ) : (
                    <span>
                        <span className="dev-compact__count" style={{ color: 'var(--warning)' }}>
                            {dirty}
                        </span>
                        <span className="dev-compact__label">Repos dirty</span>
                    </span>
                )}
                <span>
                    <span className="dev-compact__count" style={{ color: 'var(--success)' }}>
                        {containers}
                    </span>
                    <span className="dev-compact__label">Containers</span>
                </span>
            </div>
            {firstPR && (
                <div className="dev-compact__sub">
                    {liveData !== null
                        ? `${(firstPR as GithubPRLive).repo} · ${(firstPR as GithubPRLive).title}`
                        : `${data.prs[0]?.repo} · ${data.prs[0]?.title}`}
                </div>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Expanded view
// ---------------------------------------------------------------------------

function DevExpanded({
    data,
    liveData,
}: {
    data: DevToolkitMock;
    liveData: GitHubStatePayload | null;
}): ReactElement {
    return (
        <div className="dev-panel">
            {liveData !== null ? (
                <>
                    <LivePRList prs={liveData.prs} stale={liveData.stale} />
                    <LiveIssueList issues={liveData.issues} stale={liveData.stale} />
                </>
            ) : (
                <>
                    <SectionHeader
                        label="GitHub"
                        right={`${data.prs.length} PRs · ${data.notifications.length} notifs`}
                    />
                    {data.prs.map((pr) => (
                        <div
                            className="list-item"
                            key={pr.id}
                            style={{ paddingTop: 4, paddingBottom: 4 }}
                        >
                            <div
                                style={{
                                    fontSize: 11,
                                    color: 'var(--text)',
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    whiteSpace: 'nowrap',
                                }}
                            >
                                {pr.title}
                            </div>
                            <div
                                style={{
                                    fontSize: 9,
                                    color: 'var(--text-muted)',
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                }}
                            >
                                <span>
                                    {pr.repo} · {pr.author}
                                </span>
                                <span>{pr.age}</span>
                            </div>
                        </div>
                    ))}
                    {data.notifications.map((nf) => (
                        <div
                            className="list-item"
                            key={nf.id}
                            style={{ paddingTop: 4, paddingBottom: 4 }}
                        >
                            <div
                                style={{
                                    fontSize: 10,
                                    color: 'var(--text-secondary)',
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    whiteSpace: 'nowrap',
                                }}
                            >
                                [{nf.reason}] {nf.title}
                            </div>
                            <div style={{ fontSize: 9, color: 'var(--text-muted)' }}>
                                {nf.repo} · {nf.age}
                            </div>
                        </div>
                    ))}
                </>
            )}

            <SectionHeader label="Local Repos" />
            {data.repos.map((r) => (
                <div
                    className="list-item"
                    key={r.id}
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        paddingTop: 4,
                        paddingBottom: 4,
                    }}
                >
                    <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 11, color: 'var(--text)' }}>{r.name}</div>
                        <div
                            style={{
                                fontSize: 9,
                                color: 'var(--text-muted)',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                            }}
                        >
                            {r.branch}
                            {r.ahead > 0 ? ` ↑${r.ahead}` : ''}
                            {r.behind > 0 ? ` ↓${r.behind}` : ''}
                            {r.uncommitted > 0 ? ` · ${r.uncommitted} files` : ''}
                        </div>
                    </div>
                    <span className={repoPillClass(r.status)}>{r.status}</span>
                </div>
            ))}

            <SectionHeader label="Docker" right={`${data.docker.length} containers`} />
            {data.docker.map((c) => (
                <div className="list-item" key={c.id} style={{ paddingTop: 4, paddingBottom: 4 }}>
                    <div
                        style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 3 }}
                    >
                        <span
                            style={{
                                fontSize: 11,
                                color: c.status === 'running' ? 'var(--text)' : 'var(--text-muted)',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                                flex: 1,
                            }}
                        >
                            {c.name}
                        </span>
                        <span
                            className={
                                c.status === 'running'
                                    ? 'pill ok'
                                    : c.status === 'restarting'
                                      ? 'pill warn'
                                      : 'pill err'
                            }
                        >
                            {c.status}
                        </span>
                    </div>
                    <div className="dev-bar-row">
                        <span className="dev-bar-label">CPU</span>
                        <div className="bar" style={{ flex: 1 }}>
                            <div className="bar-fill" style={{ width: `${c.cpu}%` }} />
                        </div>
                        <span className="dev-bar-value">{c.cpu}%</span>
                    </div>
                    <div className="dev-bar-row">
                        <span className="dev-bar-label">MEM</span>
                        <div className="bar" style={{ flex: 1 }}>
                            <div
                                className="bar-fill"
                                style={{ width: `${c.mem}%`, background: 'var(--accent-bright)' }}
                            />
                        </div>
                        <span className="dev-bar-value">{c.mem}%</span>
                    </div>
                </div>
            ))}

            {liveData !== null ? (
                <LiveCIList ci={liveData.ci} stale={liveData.stale} />
            ) : (
                <>
                    <SectionHeader label="CI" />
                    {data.ci.map((run) => (
                        <div
                            className="list-item"
                            key={run.id}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 8,
                                paddingTop: 4,
                                paddingBottom: 4,
                            }}
                        >
                            <span className={ciPillClass(run.status)}>{run.status}</span>
                            <span style={{ fontSize: 11, color: 'var(--text)', flex: 1 }}>
                                {run.repo}
                            </span>
                            <span className="mono-small">{run.duration}</span>
                            <span className="mono-small">{relativeTime(run.ranAt)}</span>
                        </div>
                    ))}
                </>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Public export
// ---------------------------------------------------------------------------

/**
 * DevPanel — developer toolkit panel for the JARVIS HUD.
 *
 * When the backend GitHub poller is running, live PR, issue, and CI data
 * replaces the mock GitHub/CI sections. The Local Repos and Docker sections
 * always use mock data. Mock data shown for the first ~2 s while waiting.
 */
export function DevPanel({ data = devMock, mode = 'expanded' }: DevPanelProps): ReactElement {
    const { data: liveData } = useGitHubState();

    return mode === 'compact' ? (
        <DevCompact data={data} liveData={liveData} />
    ) : (
        <DevExpanded data={data} liveData={liveData} />
    );
}

export default DevPanel;
