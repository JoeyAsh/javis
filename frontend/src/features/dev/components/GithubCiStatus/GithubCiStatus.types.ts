import type { CIRun, GithubCIRunLive } from '../../types';

export interface GithubCiStatusProps {
    ci: GithubCIRunLive[] | CIRun[];
    stale?: boolean;
}
