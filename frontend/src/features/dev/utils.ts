/**
 * Dev feature utility functions.
 */
import type { CIStatus, RepoSyncStatus } from './types';
export { formatAge as relativeTime } from '@common/utils/time';

export function repoPillClass(status: RepoSyncStatus): string {
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

export function ciPillClass(status: CIStatus): string {
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
