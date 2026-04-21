/**
 * GitLabPanel — panel body for live GitLab work items.
 * Returns only body content; the Window wrapper supplies chrome via HudPanel.
 *
 * Compact mode: MR count, Issue count, first pipeline status dot.
 * Expanded mode: full lists for MRs, Issues, and Pipelines.
 *
 * Pipeline status colour convention:
 *   success  → var(--success)
 *   failed   → var(--error)
 *   running  → var(--warning)
 *   pending  → var(--warning)
 *   canceled → var(--text-muted)
 *   skipped  → var(--text-muted)
 *
 * SFX: select on pipeline row click (if opens detail) — baked into
 *      HudButton when wired; no direct SFX calls here.
 */
import type { ReactElement } from 'react';
import { useGitlabState } from '../../../hooks/useGitlabState';
import type {
  GitLabIssuePayload,
  GitLabMRPayload,
  GitLabPipelinePayload,
  GitLabStatePayload,
  PanelMode,
} from '../../../types';
import { PipelineRow } from './PipelineRow';
import './GitLabPanel.css';

export interface GitLabPanelProps {
  mode?: PanelMode;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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

type PipelineStatus = GitLabPipelinePayload['status'];

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

// ---------------------------------------------------------------------------
// Section header
// ---------------------------------------------------------------------------

function SectionHeader({ label, right }: { label: string; right?: string }): ReactElement {
  return (
    <div className="gitlab-section">
      <span className="gitlab-section__label">{label}</span>
      {right !== undefined && <span className="gitlab-section__right">{right}</span>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Compact view
// ---------------------------------------------------------------------------

function GitLabCompact({ data }: { data: GitLabStatePayload | null }): ReactElement {
  if (data === null) {
    return (
      <div className="gitlab-compact">
        <span className="gitlab-loading">Loading GitLab…</span>
      </div>
    );
  }

  if (data.error !== null && data.mrs.length === 0 && data.issues.length === 0) {
    return (
      <div className="gitlab-compact">
        <div className="gitlab-compact__row">
          <span style={{ color: 'var(--error)', fontSize: 10 }}>GitLab error</span>
          <span
            className="pill err"
            style={{ fontSize: 8 }}
            title={data.error ?? undefined}
          >
            !
          </span>
        </div>
      </div>
    );
  }

  const firstPipeline = data.pipelines[0] ?? null;

  return (
    <div className="gitlab-compact">
      <div className="gitlab-compact__row">
        <span>
          <span className="gitlab-compact__count" style={{ color: 'var(--accent-bright)' }}>
            {data.mrs.length >= 50 ? '50+' : data.mrs.length}
          </span>
          <span className="gitlab-compact__label" style={{ marginLeft: 4 }}>
            MRs
          </span>
        </span>
        <span>
          <span className="gitlab-compact__count" style={{ color: 'var(--warning)' }}>
            {data.issues.length >= 50 ? '50+' : data.issues.length}
          </span>
          <span className="gitlab-compact__label" style={{ marginLeft: 4 }}>
            Issues
          </span>
        </span>
        <span className="gitlab-compact__pipeline">
          {firstPipeline !== null ? (
            <>
              <span
                className="gitlab-pipeline-dot"
                style={{ background: pipelineColor(firstPipeline.status) }}
              />
              <span className="gitlab-compact__label">{firstPipeline.status}</span>
            </>
          ) : (
            <span className="gitlab-compact__label">—</span>
          )}
        </span>
      </div>
      {data.mrs[0] && (
        <div className="gitlab-compact__sub">
          {data.mrs[0].source_branch} · {data.mrs[0].title}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Expanded sub-sections
// ---------------------------------------------------------------------------

function MRList({ mrs }: { mrs: GitLabMRPayload[] }): ReactElement {
  return (
    <>
      <SectionHeader
        label="Merge Requests"
        right={`${mrs.length >= 50 ? '50+' : mrs.length} open`}
      />
      {mrs.slice(0, 10).map((mr) => (
        <div className="list-item" key={mr.id} style={{ paddingTop: 4, paddingBottom: 4 }}>
          <div
            style={{
              fontSize: 11,
              color: 'var(--text)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {mr.draft && (
              <span style={{ marginRight: 4, fontSize: 9, color: 'var(--text-muted)' }}>
                [DRAFT]
              </span>
            )}
            {mr.title}
          </div>
          <div
            style={{
              fontSize: 9,
              color: 'var(--text-muted)',
              display: 'flex',
              justifyContent: 'space-between',
            }}
          >
            <span>
              {mr.source_branch} · {mr.author}
            </span>
            <span>{relativeTime(mr.created_at)}</span>
          </div>
        </div>
      ))}
      {mrs.length === 0 && (
        <div className="gitlab-empty">No open MRs</div>
      )}
    </>
  );
}

function IssueList({ issues }: { issues: GitLabIssuePayload[] }): ReactElement {
  return (
    <>
      <SectionHeader
        label="Issues"
        right={`${issues.length >= 50 ? '50+' : issues.length} assigned`}
      />
      {issues.slice(0, 10).map((issue) => (
        <div className="list-item" key={issue.id} style={{ paddingTop: 4, paddingBottom: 4 }}>
          <div
            style={{
              fontSize: 11,
              color: 'var(--text)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {issue.title}
          </div>
          <div
            style={{
              fontSize: 9,
              color: 'var(--text-muted)',
              display: 'flex',
              justifyContent: 'space-between',
              gap: 4,
            }}
          >
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {issue.labels.length > 0 ? issue.labels.slice(0, 3).join(', ') : issue.author}
            </span>
            <span style={{ flexShrink: 0 }}>{relativeTime(issue.created_at)}</span>
          </div>
        </div>
      ))}
      {issues.length === 0 && (
        <div className="gitlab-empty">No assigned issues</div>
      )}
    </>
  );
}

function PipelineSection({ pipelines }: { pipelines: GitLabPipelinePayload[] }): ReactElement {
  return (
    <>
      <SectionHeader label="Pipelines" />
      {pipelines.map((p) => (
        <PipelineRow key={p.project} pipeline={p} />
      ))}
      {pipelines.length === 0 && (
        <div className="gitlab-empty">No pipelines configured</div>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Expanded view
// ---------------------------------------------------------------------------

function GitLabExpanded({ data }: { data: GitLabStatePayload | null }): ReactElement {
  if (data === null) {
    return (
      <div className="gitlab-panel">
        <span className="gitlab-loading">Waiting for GitLab data…</span>
      </div>
    );
  }

  return (
    <div className="gitlab-panel">
      {data.error !== null && (
        <div className="gitlab-error">{data.error}</div>
      )}
      <MRList mrs={data.mrs} />
      <IssueList issues={data.issues} />
      <PipelineSection pipelines={data.pipelines} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Public export
// ---------------------------------------------------------------------------

/**
 * GitLabPanel — live GitLab work-items panel for the JARVIS HUD.
 *
 * Compact mode: MR count, Issue count, first pipeline dot.
 * Expanded mode: full lists with titles, labels, branches, and relative times.
 */
export function GitLabPanel({ mode = 'expanded' }: GitLabPanelProps): ReactElement {
  const { data } = useGitlabState();

  return mode === 'compact' ? (
    <GitLabCompact data={data} />
  ) : (
    <GitLabExpanded data={data} />
  );
}

export default GitLabPanel;
