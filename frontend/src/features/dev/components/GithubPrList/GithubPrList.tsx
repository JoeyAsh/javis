import type { ReactElement } from 'react';
import type { GithubPRLive, GithubPR } from '../../types';
import { relativeTime } from '../../utils';
import { DevSectionHeader } from '../DevSectionHeader';
import type { GithubPrListProps } from './GithubPrList.types';
import styles from './GithubPrList.module.css';

function isLive(pr: GithubPRLive | GithubPR): pr is GithubPRLive {
    return 'updated_at' in pr;
}

export function GithubPrList({ prs, stale }: GithubPrListProps): ReactElement {
    return (
        <>
            <DevSectionHeader
                label="GitHub PRs"
                right={`${prs.length} open`}
                stale={stale}
            />
            {prs.slice(0, 3).map((pr) => (
                <div className={`list-item ${styles.row}`} key={pr.id}>
                    <div className={styles.title}>{pr.title}</div>
                    <div className={styles.meta}>
                        <span>
                            {pr.repo} · {pr.author}
                        </span>
                        <span>{isLive(pr) ? relativeTime(pr.updated_at) : pr.age}</span>
                    </div>
                </div>
            ))}
            {prs.length === 0 && (
                <div className={`list-item ${styles.empty}`}>No open PRs</div>
            )}
        </>
    );
}

export default GithubPrList;
