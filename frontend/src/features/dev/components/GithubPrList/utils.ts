import type { GithubPRLive, GithubPR } from '../../types';

export function isLive(pr: GithubPRLive | GithubPR): pr is GithubPRLive {
    return 'updated_at' in pr;
}
