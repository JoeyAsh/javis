import { formatTime } from '@common/utils/time';
import type { GitLabPipelinePayload } from '../../types';
import styles from './PipelineRow.module.css';

export type PipelineStatus = GitLabPipelinePayload['status'];

export { formatTime };

export function pillClass(status: PipelineStatus): string {
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

export function pillLabel(status: PipelineStatus): string {
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
