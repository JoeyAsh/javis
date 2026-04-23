import type { ReactElement } from 'react';
import { usePanelAvailable } from '@app/providers/PanelAvailabilityProvider';
import { useGitlab } from '../../hooks/useGitlab';
import { PipelineRow } from '../PipelineRow';
import type { GitLabPanelProps, GitLabCompactProps, GitLabExpandedProps } from './GitLabPanel.types';
import styles from './GitLabPanel.module.css';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

type PipelineStatus =
    | 'success'
    | 'failed'
    | 'running'
    | 'pending'
    | 'canceled'
    | 'skipped'
    | string;

function pipelineColor(status: PipelineStatus): string {
    switch (status) {
        case 'success':
            return 'var(--success)';
        case 'failed':
            return 'var(--error)';
        case 'running':
        case 'pending':
            return 'var(--warning)';
        default:
            return 'var(--text-muted)';
    }
}

// ---------------------------------------------------------------------------
// Compact view
// ---------------------------------------------------------------------------

function GitLabCompact({ data }: GitLabCompactProps): ReactElement {
    if (data === null) {
        return (
            <div className={styles.compact}>
                <span className={styles.loading}>Loading GitLab…</span>
            </div>
        );
    }

    if (data.error !== null && data.mrs.length === 0 && data.issues.length === 0) {
        return (
            <div className={styles.compact}>
                <div className={styles.compactRow}>
                    <span style={{ color: 'var(--error)', fontSize: 10 }}>GitLab error</span>
                    <span className={styles.errorPill} title={data.error ?? undefined}>!</span>
                </div>
            </div>
        );
    }

    const firstPipeline = data.pipelines[0] ?? null;

    return (
        <div className={styles.compact}>
            <div className={styles.compactRow}>
                <span>
                    <span className={styles.count} style={{ color: 'var(--accent-bright)' }}>
                        {data.mrs.length >= 50 ? '50+' : data.mrs.length}
                    </span>
                    <span className={styles.label} style={{ marginLeft: 4 }}>MRs</span>
                </span>
                <span>
                    <span className={styles.count} style={{ color: 'var(--warning)' }}>
                        {data.issues.length >= 50 ? '50+' : data.issues.length}
                    </span>
                    <span className={styles.label} style={{ marginLeft: 4 }}>Issues</span>
                </span>
                <span className={styles.pipelineGroup}>
                    {firstPipeline !== null ? (
                        <>
                            <span
                                className={styles.pipelineDot}
                                style={{ background: pipelineColor(firstPipeline.status) }}
                            />
                            <span className={styles.label}>{firstPipeline.status}</span>
                        </>
                    ) : (
                        <span className={styles.label}>—</span>
                    )}
                </span>
            </div>
            {data.mrs[0] && (
                <div className={styles.compactSub}>
                    {data.mrs[0].source_branch} · {data.mrs[0].title}
                </div>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Expanded view
// ---------------------------------------------------------------------------

function GitLabExpanded({ data }: GitLabExpandedProps): ReactElement {
    if (data === null) {
        return (
            <div className={styles.panel}>
                <span className={styles.loading}>Waiting for GitLab data…</span>
            </div>
        );
    }

    return (
        <div className={styles.panel}>
            {data.error !== null && <div className={styles.error}>{data.error}</div>}
            {data.pipelines.slice(0, 3).map((p) => (
                <PipelineRow key={p.project} pipeline={p} />
            ))}
            {data.pipelines.length === 0 && data.error === null && (
                <div className={styles.empty}>No pipelines configured</div>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Public export
// ---------------------------------------------------------------------------

export function GitLabPanel({ mode = 'expanded' }: GitLabPanelProps): ReactElement {
    const { state, loading } = useGitlab();

    usePanelAvailable('gitlab', !loading || state !== null);

    if (loading && state === null) {
        return mode === 'compact' ? (
            <div className={styles.compact}>
                <span className={styles.loading}>Loading GitLab…</span>
            </div>
        ) : (
            <div className={styles.panel}>
                <span className={styles.loading}>Waiting for GitLab data…</span>
            </div>
        );
    }

    return mode === 'compact' ? (
        <GitLabCompact data={state} />
    ) : (
        <GitLabExpanded data={state} />
    );
}

export default GitLabPanel;
