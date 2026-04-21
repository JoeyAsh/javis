/**
 * PipelineRow — a single pipeline entry row.
 * Matches prototype GitlabPanel `.ev` pattern:
 *   time  (pipeline id · time, accent-bright, font-size 10)
 *   tx    (project name · branch muted)
 *   pil   (status pill — passed=on/success, running=n/accent, failed=err/red)
 */
import type { ReactElement } from 'react';
import type { GitLabPipelinePayload } from '../../../types';
import './GitLabPanel.css';

export interface PipelineRowProps {
    pipeline: GitLabPipelinePayload;
}

type PipelineStatus = GitLabPipelinePayload['status'];

function formatTime(iso: string): string {
    if (!iso) return '';
    const d = new Date(iso);
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function pipelinePillClass(status: PipelineStatus): string {
    switch (status) {
        case 'success':
            return 'gitlab-pipeline-pill gitlab-pipeline-pill--passed';
        case 'failed':
            return 'gitlab-pipeline-pill gitlab-pipeline-pill--failed';
        case 'running':
        case 'pending':
            return 'gitlab-pipeline-pill gitlab-pipeline-pill--running';
        default:
            return 'gitlab-pipeline-pill';
    }
}

function pillLabel(status: PipelineStatus): string {
    switch (status) {
        case 'success':
            return 'passed';
        case 'failed':
            return 'failed';
        case 'running':
            return 'running';
        case 'pending':
            return 'pending';
        default:
            return status;
    }
}

export function PipelineRow({ pipeline }: PipelineRowProps): ReactElement {
    const timeStr = formatTime(pipeline.created_at);

    // Split project path: last segment = name, second-to-last = namespace/branch context
    const projParts = pipeline.project.split('/');
    const projName = projParts[projParts.length - 1] ?? pipeline.project;
    const branch = projParts.length > 1 ? projParts.slice(0, -1).join('/') + '/main' : 'main';

    return (
        <div className="gitlab-pipeline-row">
            <span className="gitlab-pipeline-row__time">{timeStr}</span>
            <div className="gitlab-pipeline-row__tx">
                <div className="gitlab-pipeline-row__proj">
                    {projName} <span className="gitlab-pipeline-row__branch">· {branch}</span>
                </div>
            </div>
            <span className={pipelinePillClass(pipeline.status)}>{pillLabel(pipeline.status)}</span>
        </div>
    );
}

export default PipelineRow;
