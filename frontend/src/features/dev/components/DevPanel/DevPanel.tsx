/**
 * DevPanel — developer toolkit panel for the JARVIS HUD.
 *
 * Compact: summary counts + first PR title.
 * Expanded: GitHub PRs/Issues/CI (live when available), Local Repos, Docker.
 */
import type { ReactElement } from 'react';
import { useDev } from '../../hooks/useDev';
import type { GithubPRLive } from '../../types';
import { GithubPrList } from '../GithubPrList';
import { GithubIssueList } from '../GithubIssueList';
import { GithubCiStatus } from '../GithubCiStatus';
import { LocalReposList } from '../LocalReposList';
import { DockerContainersList } from '../DockerContainersList';
import { DevSectionHeader } from '../DevSectionHeader';
import type { DevPanelProps, DevCompactProps, DevExpandedProps } from './DevPanel.types';
import styles from './DevPanel.module.css';

// ── Compact view ─────────────────────────────────────────────────────────────

function DevCompact({ data, liveData }: DevCompactProps): ReactElement {
    const prs = liveData !== null ? liveData.prs.length : data.prs.length;
    const issues = liveData !== null ? liveData.issues.length : 0;
    const dirty = data.repos.filter((r) => r.status === 'dirty' || r.status === 'behind').length;
    const containers = data.docker.filter((c) => c.status === 'running').length;
    const firstPR = liveData !== null ? liveData.prs[0] : data.prs[0];

    return (
        <div className={styles.compact}>
            <div className={styles.compactRow}>
                <span>
                    <span className={`${styles.compactCount} ${styles.compactCountPrs}`}>{prs}</span>
                    <span className={styles.compactLabel}>PRs</span>
                </span>
                {liveData !== null ? (
                    <span>
                        <span className={`${styles.compactCount} ${styles.compactCountWarn}`}>
                            {issues}
                        </span>
                        <span className={styles.compactLabel}>Issues</span>
                    </span>
                ) : (
                    <span>
                        <span className={`${styles.compactCount} ${styles.compactCountWarn}`}>
                            {dirty}
                        </span>
                        <span className={styles.compactLabel}>Repos dirty</span>
                    </span>
                )}
                <span>
                    <span className={`${styles.compactCount} ${styles.compactCountOk}`}>
                        {containers}
                    </span>
                    <span className={styles.compactLabel}>Containers</span>
                </span>
            </div>
            {firstPR !== undefined && (
                <div className={styles.compactSub}>
                    {liveData !== null
                        ? `${(firstPR as GithubPRLive).repo} · ${(firstPR as GithubPRLive).title}`
                        : `${data.prs[0]?.repo} · ${data.prs[0]?.title}`}
                </div>
            )}
        </div>
    );
}

// ── Expanded view ─────────────────────────────────────────────────────────────

function DevExpanded({ data, liveData }: DevExpandedProps): ReactElement {
    return (
        <div className={styles.panel}>
            {liveData !== null ? (
                <>
                    <GithubPrList prs={liveData.prs} stale={liveData.stale} />
                    <GithubIssueList issues={liveData.issues} stale={liveData.stale} />
                </>
            ) : (
                <>
                    <DevSectionHeader
                        label="GitHub"
                        right={`${data.prs.length} PRs · ${data.notifications.length} notifs`}
                    />
                    {data.prs.map((pr) => (
                        <div className={`list-item ${styles.mockPrRow}`} key={pr.id}>
                            <div className={styles.mockPrTitle}>{pr.title}</div>
                            <div className={styles.mockPrMeta}>
                                <span>
                                    {pr.repo} · {pr.author}
                                </span>
                                <span>{pr.age}</span>
                            </div>
                        </div>
                    ))}
                    {data.notifications.map((nf) => (
                        <div className={`list-item ${styles.notifRow}`} key={nf.id}>
                            <div className={styles.notifTitle}>
                                [{nf.reason}] {nf.title}
                            </div>
                            <div className={styles.notifMeta}>
                                {nf.repo} · {nf.age}
                            </div>
                        </div>
                    ))}
                </>
            )}

            <LocalReposList repos={data.repos} />
            <DockerContainersList containers={data.docker} />

            {liveData !== null ? (
                <GithubCiStatus ci={liveData.ci} stale={liveData.stale} />
            ) : (
                <GithubCiStatus ci={data.ci} />
            )}
        </div>
    );
}

// ── Public component ──────────────────────────────────────────────────────────

export function DevPanel({ data, mode = 'expanded' }: DevPanelProps): ReactElement {
    const { liveData, mockData } = useDev();
    const effectiveData = data ?? mockData;

    return mode === 'compact' ? (
        <DevCompact data={effectiveData} liveData={liveData} />
    ) : (
        <DevExpanded data={effectiveData} liveData={liveData} />
    );
}

export default DevPanel;
