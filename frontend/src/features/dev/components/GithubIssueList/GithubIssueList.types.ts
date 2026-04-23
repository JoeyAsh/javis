import type { GithubIssueLive } from '../../types';

export interface GithubIssueListProps {
    issues: GithubIssueLive[];
    stale?: boolean;
}
