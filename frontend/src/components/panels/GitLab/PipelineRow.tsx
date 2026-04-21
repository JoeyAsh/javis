/**
 * PipelineRow — a single pipeline entry row.
 * Status dot + badge + project name + relative time.
 */
import type { ReactElement } from 'react';
import type { GitLabPipelinePayload } from '../../../types';
import './GitLabPanel.css';

export interface PipelineRowProps {
  pipeline: GitLabPipelinePayload;
}

type PipelineStatus = GitLabPipelinePayload['status'];

function relativeTime(iso: string): string {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return 'now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function pipelineColor(status: PipelineStatus): string {
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

function pipelinePillClass(status: PipelineStatus): string {
  switch (status) {
    case 'success':
      return 'pill ok';
    case 'failed':
      return 'pill err';
    case 'running':
    case 'pending':
      return 'pill warn';
    default:
      return 'pill';
  }
}

export function PipelineRow({ pipeline }: PipelineRowProps): ReactElement {
  return (
    <div className="gitlab-pipeline-row">
      <span
        className="gitlab-pipeline-dot"
        style={{ background: pipelineColor(pipeline.status) }}
      />
      <span className={pipelinePillClass(pipeline.status)}>{pipeline.status}</span>
      <span
        style={{
          fontSize: 11,
          color: 'var(--text)',
          flex: 1,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {pipeline.project}
      </span>
      <span className="mono-small" style={{ flexShrink: 0 }}>
        {relativeTime(pipeline.created_at)}
      </span>
    </div>
  );
}

export default PipelineRow;
