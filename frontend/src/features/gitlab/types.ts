/**
 * GitLab feature types.
 */

/** A single open GitLab merge request assigned to the authenticated user. */
export interface GitLabMRPayload {
    id: number;
    iid: number;
    title: string;
    source_branch: string;
    web_url: string;
    author: string;
    created_at: string; // ISO 8601
    draft: boolean;
}

/** A single open GitLab issue assigned to the authenticated user. */
export interface GitLabIssuePayload {
    id: number;
    iid: number;
    title: string;
    labels: string[];
    web_url: string;
    author: string;
    created_at: string; // ISO 8601
}

/** The most recent pipeline for a configured project. */
export interface GitLabPipelinePayload {
    project: string;
    status: 'success' | 'failed' | 'running' | 'pending' | 'canceled' | 'skipped';
    web_url: string;
    created_at: string; // ISO 8601
}

/**
 * Broadcast every `poll_interval_seconds` from the backend GitLab poller.
 * `error` is non-null when the last fetch failed (partially or completely).
 */
export interface GitLabStatePayload {
    mrs: GitLabMRPayload[];
    issues: GitLabIssuePayload[];
    pipelines: GitLabPipelinePayload[];
    error: string | null;
}
