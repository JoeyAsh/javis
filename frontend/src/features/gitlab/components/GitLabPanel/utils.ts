export type PipelineStatus =
    | 'success'
    | 'failed'
    | 'running'
    | 'pending'
    | 'canceled'
    | 'skipped'
    | string;

export function pipelineColor(status: PipelineStatus): string {
    switch (status) {
        case 'success':
            return 'var(--success)';
        case 'failed':
            return 'var(--error)';
        case 'running':
        case 'pending':
            return 'var(--warning)';
        default:
            return 'var(--text-muted)';
    }
}
