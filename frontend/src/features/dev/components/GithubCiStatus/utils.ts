import type { GithubCIRunLive, CIRun } from '../../types';

export function isLive(run: GithubCIRunLive | CIRun): run is GithubCIRunLive {
    return 'ran_at' in run;
}

export function getKey(run: GithubCIRunLive | CIRun): string {
    return isLive(run) ? run.repo : run.id;
}
