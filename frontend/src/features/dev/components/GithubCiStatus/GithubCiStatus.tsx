import type { ReactElement } from 'react';
import type { GithubCIRunLive, CIRun } from '../../types';
import { ciPillClass, relativeTime } from '../../utils';
import { DevSectionHeader } from '../DevSectionHeader';
import type { GithubCiStatusProps } from './GithubCiStatus.types';
import styles from './GithubCiStatus.module.css';

function isLive(run: GithubCIRunLive | CIRun): run is GithubCIRunLive {
    return 'ran_at' in run;
}

function getKey(run: GithubCIRunLive | CIRun): string {
    return isLive(run) ? run.repo : run.id;
}

export function GithubCiStatus({ ci, stale }: GithubCiStatusProps): ReactElement {
    return (
        <>
            <DevSectionHeader label="CI" stale={stale} />
            {ci.map((run) => (
                <div className={`list-item ${styles.row}`} key={getKey(run)}>
                    <span className={ciPillClass(run.status)}>{run.status}</span>
                    <span className={styles.repoName}>{run.repo}</span>
                    {isLive(run) ? (
                        <span className="mono-small">{relativeTime(run.ran_at)}</span>
                    ) : (
                        <>
                            <span className="mono-small">{run.duration}</span>
                            <span className="mono-small">{relativeTime(run.ranAt)}</span>
                        </>
                    )}
                </div>
            ))}
            {ci.length === 0 && (
                <div className={`list-item ${styles.empty}`}>No CI runs</div>
            )}
        </>
    );
}

export default GithubCiStatus;
