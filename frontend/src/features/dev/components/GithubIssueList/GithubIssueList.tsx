import type { ReactElement } from 'react';
import { relativeTime } from '../../utils';
import { DevSectionHeader } from '../DevSectionHeader';
import type { GithubIssueListProps } from './GithubIssueList.types';
import styles from './GithubIssueList.module.css';

export function GithubIssueList({ issues, stale }: GithubIssueListProps): ReactElement {
    return (
        <>
            <DevSectionHeader
                label="GitHub Issues"
                right={`${issues.length} assigned`}
                stale={stale}
            />
            {issues.slice(0, 3).map((issue) => (
                <div className={`list-item ${styles.row}`} key={issue.id}>
                    <div className={styles.title}>{issue.title}</div>
                    <div className={styles.meta}>
                        <span>{issue.repo}</span>
                        <span>{relativeTime(issue.updated_at)}</span>
                    </div>
                </div>
            ))}
            {issues.length === 0 && (
                <div className={`list-item ${styles.empty}`}>No assigned issues</div>
            )}
        </>
    );
}

export default GithubIssueList;
