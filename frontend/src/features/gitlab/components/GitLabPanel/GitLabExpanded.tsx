import type { ReactElement } from 'react';
import { PipelineRow } from '../PipelineRow';
import type { GitLabExpandedProps } from './GitLabPanel.types';
import styles from './GitLabPanel.module.css';

export function GitLabExpanded({ data }: GitLabExpandedProps): ReactElement {
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

export default GitLabExpanded;
