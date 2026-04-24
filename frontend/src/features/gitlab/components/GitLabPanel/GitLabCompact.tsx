import type { ReactElement } from 'react';
import type { GitLabCompactProps } from './GitLabPanel.types';
import { pipelineColor } from './utils';
import styles from './GitLabPanel.module.css';

export function GitLabCompact({ data }: GitLabCompactProps): ReactElement {
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
                    <span className="text-[10px] text-[var(--error)]">GitLab error</span>
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
                    <span className={`${styles.count} text-[var(--accent-bright)]`}>
                        {data.mrs.length >= 50 ? '50+' : data.mrs.length}
                    </span>
                    <span className={`${styles.label} ml-1`}>MRs</span>
                </span>
                <span>
                    <span className={`${styles.count} text-[var(--warning)]`}>
                        {data.issues.length >= 50 ? '50+' : data.issues.length}
                    </span>
                    <span className={`${styles.label} ml-1`}>Issues</span>
                </span>
                <span className={styles.pipelineGroup}>
                    {firstPipeline !== null ? (
                        <>
                            <span
                                className={styles.pipelineDot}
                                style={{ background: pipelineColor(firstPipeline.status) } as React.CSSProperties}
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

export default GitLabCompact;
