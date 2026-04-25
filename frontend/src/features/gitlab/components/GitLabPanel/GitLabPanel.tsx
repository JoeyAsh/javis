import type { ReactElement } from 'react';
import { usePanelAvailable } from '@app/providers/PanelAvailabilityProvider';
import { useGitlab } from '../../hooks/useGitlab';
import { GitLabCompact } from './GitLabCompact';
import { GitLabExpanded } from './GitLabExpanded';
import type { GitLabPanelProps } from './GitLabPanel.types';
import styles from './GitLabPanel.module.css';

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
