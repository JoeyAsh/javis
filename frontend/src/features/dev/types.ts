/**
 * Dev feature types.
 * Moved from src/types.ts — covers GitHub, repos, docker, CI.
 */

export interface GithubPR {
    id: string;
    repo: string;
    title: string;
    author: string;
    age: string;
}

export interface GithubNotification {
    id: string;
    repo: string;
    reason: string;
    title: string;
    age: string;
}

export interface GithubPRLive {
    id: string;
    repo: string;
    title: string;
    author: string;
    html_url: string;
    updated_at: string; // ISO
}

export interface GithubIssueLive {
    id: string;
    repo: string;
    title: string;
    html_url: string;
    updated_at: string; // ISO
}

export interface GithubCIRunLive {
    repo: string;
    status: 'success' | 'failure' | 'running' | 'pending';
    ran_at: string; // ISO
    html_url: string;
}

export type RepoSyncStatus = 'clean' | 'dirty' | 'ahead' | 'behind';

export interface LocalRepo {
    id: string;
    name: string;
    branch: string;
    status: RepoSyncStatus;
    ahead: number;
    behind: number;
    uncommitted: number;
}

export interface DockerContainer {
    id: string;
    name: string;
    image: string;
    status: 'running' | 'exited' | 'restarting';
    cpu: number; // 0-100
    mem: number; // 0-100
}

export type CIStatus = 'success' | 'failure' | 'running' | 'pending';

export interface CIRun {
    id: string;
    repo: string;
    status: CIStatus;
    ranAt: string; // ISO
    duration: string;
}

export interface DevToolkitMock {
    prs: GithubPR[];
    notifications: GithubNotification[];
    repos: LocalRepo[];
    docker: DockerContainer[];
    ci: CIRun[];
}

/**
 * Broadcast every `poll_interval_seconds` from the backend GitHub poller.
 * `stale: true` means the last poll failed and this is cached data.
 */
export interface GitHubStatePayload {
    prs: GithubPRLive[];
    issues: GithubIssueLive[];
    ci: GithubCIRunLive[];
    fetched_at: string; // ISO
    stale: boolean;
}
