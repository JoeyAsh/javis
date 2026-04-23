/**
 * Dev feature utility functions.
 */
import type { CIStatus, RepoSyncStatus } from './types';

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

export function relativeTime(iso: string): string {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60_000);
    if (mins < 1) return 'now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
}
