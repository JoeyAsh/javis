import type { ReactElement } from 'react';
import type { GitLabPipelinePayload } from '../../types';
import type { PipelineRowProps } from './PipelineRow.types';
import styles from './PipelineRow.module.css';

type PipelineStatus = GitLabPipelinePayload['status'];

function formatTime(iso: string): string {
    if (!iso) return '';
    const d = new Date(iso);
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function pillClass(status: PipelineStatus): string {
    switch (status) {
        case 'success':
            return `${styles.pill} ${styles.pillPassed}`;
        case 'failed':
            return `${styles.pill} ${styles.pillFailed}`;
        case 'running':
        case 'pending':
            return `${styles.pill} ${styles.pillRunning}`;
        default:
            return styles.pill;
    }
}

function pillLabel(status: PipelineStatus): string {
    switch (status) {
        case 'success':
            return 'passed';
        case 'failed':
            return 'failed';
        case 'running':
            return 'running';
        case 'pending':
            return 'pending';
        default:
            return status;
    }
}

export function PipelineRow({ pipeline }: PipelineRowProps): ReactElement {
    const timeStr = formatTime(pipeline.created_at);

    const projParts = pipeline.project.split('/');
    const projName = projParts[projParts.length - 1] ?? pipeline.project;
    const branch = projParts.length > 1 ? projParts.slice(0, -1).join('/') + '/main' : 'main';

    return (
        <div className={styles.row}>
            <span className={styles.time}>{timeStr}</span>
            <div className={styles.tx}>
                <div className={styles.proj}>
                    {projName}{' '}
                    <span className={styles.branch}>· {branch}</span>
                </div>
            </div>
            <span className={pillClass(pipeline.status)}>{pillLabel(pipeline.status)}</span>
        </div>
    );
}

export default PipelineRow;
