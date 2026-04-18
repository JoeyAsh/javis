/**
 * GitLabPanel — HUD panel for live GitLab work items.
 *
 * Compact mode: MR count, Issue count, first pipeline status dot.
 * Expanded mode: full lists for MRs, Issues, and Pipelines.
 *
 * Follows the same design-system conventions as DevPanel: JetBrains Mono,
 * CSS vars, `window-compact-row`, `list-item`, `pill` classes.
 *
 * Pipeline status colour convention:
 *   success  → var(--success)  (green)
 *   failed   → var(--error)    (red)
 *   running  → var(--warning)  (amber)
 *   pending  → var(--warning)  (amber)
 *   canceled → var(--text-muted) (grey)
 *   skipped  → var(--text-muted) (grey)
 */
import type { CSSProperties, ReactElement } from 'react';
import { useGitlabState } from '../../hooks/useGitlabState';
import type {
  GitLabIssuePayload,
  GitLabMRPayload,
  GitLabPipelinePayload,
  GitLabStatePayload,
  PanelMode,
} from '../../types';

export interface GitLabPanelProps {
  mode?: PanelMode;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function relativeTime(iso: string): string {
  /** Return a compact relative-time string for an ISO timestamp. */
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
  /** Return the CSS colour variable for a pipeline status. */
  switch (status) {
    case 'success':
      return 'var(--success)';
    case 'failed':
      return 'var(--error, #f44)';
    case 'running':
    case 'pending':
      return 'var(--warning)';
    default:
      return 'var(--text-muted)';
  }
}

function pipelinePillClass(status: PipelineStatus): string {
  /** Return a `pill` class for a pipeline status badge. */
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

const DOT_STYLE: CSSProperties = {
  display: 'inline-block',
  width: 8,
  height: 8,
  borderRadius: '50%',
  flexShrink: 0,
};

// ---------------------------------------------------------------------------
// Section header (matches DevPanel's SectionHeader)
// ---------------------------------------------------------------------------

function SectionHeader({ label, right }: { label: string; right?: string }): ReactElement {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'baseline',
        marginTop: 8,
        marginBottom: 6,
      }}
    >
      <span
        style={{
          fontSize: 9,
          letterSpacing: 2,
          textTransform: 'uppercase',
          color: 'var(--accent)',
          fontWeight: 600,
        }}
      >
        {label}
      </span>
      {right !== undefined && <span className="mono-small">{right}</span>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Compact view
// ---------------------------------------------------------------------------

function GitLabCompact({ data }: { data: GitLabStatePayload | null }): ReactElement {
  /** Compact three-item row: MR count, Issue count, first pipeline dot. */
  if (data === null) {
    return (
      <div className="window-compact-row" style={{ fontSize: 10, color: 'var(--text-muted)' }}>
        Loading GitLab…
      </div>
    );
  }

  if (data.error !== null && data.mrs.length === 0 && data.issues.length === 0) {
    return (
      <div className="window-compact-row" style={{ fontSize: 10, color: 'var(--error, #f44)' }}>
        <span>GitLab error</span>
        <span
          className="pill err"
          style={{ marginLeft: 6, fontSize: 8 }}
          title={data.error ?? undefined}
        >
          !
        </span>
      </div>
    );
  }

  const firstPipeline = data.pipelines[0] ?? null;

  return (
    <>
      <div className="window-compact-row" style={{ gap: 10, fontSize: 11 }}>
        <span>
          <span style={{ color: 'var(--accent-bright)', fontWeight: 500 }}>
            {data.mrs.length >= 50 ? '50+' : data.mrs.length}
          </span>
          <span className="mono-small" style={{ marginLeft: 4 }}>
            MRs
          </span>
        </span>
        <span>
          <span style={{ color: 'var(--warning)', fontWeight: 500 }}>
            {data.issues.length >= 50 ? '50+' : data.issues.length}
          </span>
          <span className="mono-small" style={{ marginLeft: 4 }}>
            Issues
          </span>
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          {firstPipeline !== null ? (
            <>
              <span
                style={{
                  ...DOT_STYLE,
                  background: pipelineColor(firstPipeline.status),
                }}
              />
              <span className="mono-small">{firstPipeline.status}</span>
            </>
          ) : (
            <span className="mono-small" style={{ color: 'var(--text-muted)' }}>
              —
            </span>
          )}
        </span>
      </div>
      {data.mrs[0] && (
        <div
          className="window-compact-row truncate"
          style={{ fontSize: 10, color: 'var(--text-muted)' }}
        >
          {data.mrs[0].source_branch} · {data.mrs[0].title}
        </div>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Expanded sub-sections
// ---------------------------------------------------------------------------

function MRList({ mrs }: { mrs: GitLabMRPayload[] }): ReactElement {
  /** Full MR list rows: title + source branch + author + relative time. */
  return (
    <>
      <SectionHeader label="Merge Requests" right={`${mrs.length >= 50 ? '50+' : mrs.length} open`} />
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
              <span
                style={{ marginRight: 4, fontSize: 9, color: 'var(--text-muted)' }}
              >
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
        <div
          className="list-item"
          style={{ fontSize: 10, color: 'var(--text-muted)', paddingTop: 4 }}
        >
          No open MRs
        </div>
      )}
    </>
  );
}

function IssueList({ issues }: { issues: GitLabIssuePayload[] }): ReactElement {
  /** Full Issue list rows: title + labels + author + relative time. */
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
        <div
          className="list-item"
          style={{ fontSize: 10, color: 'var(--text-muted)', paddingTop: 4 }}
        >
          No assigned issues
        </div>
      )}
    </>
  );
}

function PipelineList({ pipelines }: { pipelines: GitLabPipelinePayload[] }): ReactElement {
  /** Pipeline status row per project. */
  return (
    <>
      <SectionHeader label="Pipelines" />
      {pipelines.map((p) => (
        <div
          className="list-item"
          key={p.project}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            paddingTop: 4,
            paddingBottom: 4,
          }}
        >
          <span
            style={{ ...DOT_STYLE, background: pipelineColor(p.status), flexShrink: 0 }}
          />
          <span className={pipelinePillClass(p.status)}>{p.status}</span>
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
            {p.project}
          </span>
          <span className="mono-small" style={{ flexShrink: 0 }}>
            {relativeTime(p.created_at)}
          </span>
        </div>
      ))}
      {pipelines.length === 0 && (
        <div
          className="list-item"
          style={{ fontSize: 10, color: 'var(--text-muted)', paddingTop: 4 }}
        >
          No pipelines configured
        </div>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Expanded view
// ---------------------------------------------------------------------------

function GitLabExpanded({ data }: { data: GitLabStatePayload | null }): ReactElement {
  /** Full expanded view with all three sections. */
  if (data === null) {
    return (
      <div style={{ fontSize: 11, color: 'var(--text-muted)', padding: '8px 0' }}>
        Waiting for GitLab data…
      </div>
    );
  }

  return (
    <>
      {data.error !== null && (
        <div
          style={{
            fontSize: 10,
            color: 'var(--error, #f44)',
            background: 'rgba(255,68,68,0.08)',
            borderRadius: 4,
            padding: '4px 6px',
            marginBottom: 4,
          }}
        >
          {data.error}
        </div>
      )}
      <MRList mrs={data.mrs} />
      <IssueList issues={data.issues} />
      <PipelineList pipelines={data.pipelines} />
    </>
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
 *
 * When the backend GitLab poller is disabled or no token is configured, the
 * panel shows a muted placeholder message.
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
