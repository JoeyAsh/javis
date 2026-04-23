import type { GithubPR, GithubPRLive } from '../../types';

export interface GithubPrListProps {
    prs: GithubPRLive[] | GithubPR[];
    stale?: boolean;
}
