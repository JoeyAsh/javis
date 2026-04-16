import type { ReactElement } from 'react';
import { devMock } from '../../mock/devMock';
import type {
  DevToolkitMock,
  RepoSyncStatus,
  CIStatus,
  PanelMode,
} from '../../types';

export interface DevPanelProps {
  data?: DevToolkitMock;
  mode?: PanelMode;
}

function repoPillClass(status: RepoSyncStatus): string {
  switch (status) {
    case 'clean':
      return 'pill ok';
    case 'dirty':
      return 'pill warn';
    case 'behind':
      return 'pill err';
    case 'ahead':
      return 'pill info';
  }
}

function ciPillClass(status: CIStatus): string {
  switch (status) {
    case 'success':
      return 'pill ok';
    case 'failure':
      return 'pill err';
    case 'running':
      return 'pill info';
    case 'pending':
      return 'pill';
  }
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return 'now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

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

function DevCompact({ data }: { data: DevToolkitMock }): ReactElement {
  const prs = data.prs.length;
  const dirty = data.repos.filter((r) => r.status === 'dirty' || r.status === 'behind').length;
  const containers = data.docker.filter((c) => c.status === 'running').length;
  return (
    <>
      <div className="window-compact-row" style={{ gap: 10, fontSize: 11 }}>
        <span>
          <span style={{ color: 'var(--accent-bright)', fontWeight: 500 }}>{prs}</span>
          <span className="mono-small" style={{ marginLeft: 4 }}>PRs</span>
        </span>
        <span>
          <span style={{ color: 'var(--warning)', fontWeight: 500 }}>{dirty}</span>
          <span className="mono-small" style={{ marginLeft: 4 }}>Repos dirty</span>
        </span>
        <span>
          <span style={{ color: 'var(--success)', fontWeight: 500 }}>{containers}</span>
          <span className="mono-small" style={{ marginLeft: 4 }}>Containers</span>
        </span>
      </div>
      {data.prs[0] && (
        <div
          className="window-compact-row truncate"
          style={{ fontSize: 10, color: 'var(--text-muted)' }}
        >
          {data.prs[0].repo} · {data.prs[0].title}
        </div>
      )}
    </>
  );
}

function DevExpanded({ data }: { data: DevToolkitMock }): ReactElement {
  return (
    <>
      <SectionHeader
        label="GitHub"
        right={`${data.prs.length} PRs · ${data.notifications.length} notifs`}
      />
      {data.prs.map((pr) => (
        <div className="list-item" key={pr.id} style={{ paddingTop: 4, paddingBottom: 4 }}>
          <div
            style={{
              fontSize: 11,
              color: 'var(--text)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {pr.title}
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
              {pr.repo} · {pr.author}
            </span>
            <span>{pr.age}</span>
          </div>
        </div>
      ))}
      {data.notifications.map((nf) => (
        <div className="list-item" key={nf.id} style={{ paddingTop: 4, paddingBottom: 4 }}>
          <div
            style={{
              fontSize: 10,
              color: 'var(--text-secondary)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            [{nf.reason}] {nf.title}
          </div>
          <div style={{ fontSize: 9, color: 'var(--text-muted)' }}>
            {nf.repo} · {nf.age}
          </div>
        </div>
      ))}

      <SectionHeader label="Local Repos" />
      {data.repos.map((r) => (
        <div
          className="list-item"
          key={r.id}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            paddingTop: 4,
            paddingBottom: 4,
          }}
        >
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 11, color: 'var(--text)' }}>{r.name}</div>
            <div
              style={{
                fontSize: 9,
                color: 'var(--text-muted)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {r.branch}
              {r.ahead > 0 ? ` ↑${r.ahead}` : ''}
              {r.behind > 0 ? ` ↓${r.behind}` : ''}
              {r.uncommitted > 0 ? ` · ${r.uncommitted} files` : ''}
            </div>
          </div>
          <span className={repoPillClass(r.status)}>{r.status}</span>
        </div>
      ))}

      <SectionHeader label="Docker" right={`${data.docker.length} containers`} />
      {data.docker.map((c) => (
        <div className="list-item" key={c.id} style={{ paddingTop: 4, paddingBottom: 4 }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'baseline',
              gap: 6,
              marginBottom: 3,
            }}
          >
            <span
              style={{
                fontSize: 11,
                color: c.status === 'running' ? 'var(--text)' : 'var(--text-muted)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                flex: 1,
              }}
            >
              {c.name}
            </span>
            <span
              className={
                c.status === 'running'
                  ? 'pill ok'
                  : c.status === 'restarting'
                    ? 'pill warn'
                    : 'pill err'
              }
            >
              {c.status}
            </span>
          </div>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <span className="mono-small" style={{ width: 24 }}>
              CPU
            </span>
            <div className="bar" style={{ flex: 1 }}>
              <div className="bar-fill" style={{ width: `${c.cpu}%` }} />
            </div>
            <span className="mono-small" style={{ width: 26, textAlign: 'right' }}>
              {c.cpu}%
            </span>
          </div>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginTop: 3 }}>
            <span className="mono-small" style={{ width: 24 }}>
              MEM
            </span>
            <div className="bar" style={{ flex: 1 }}>
              <div
                className="bar-fill"
                style={{ width: `${c.mem}%`, background: 'var(--accent-bright)' }}
              />
            </div>
            <span className="mono-small" style={{ width: 26, textAlign: 'right' }}>
              {c.mem}%
            </span>
          </div>
        </div>
      ))}

      <SectionHeader label="CI" />
      {data.ci.map((run) => (
        <div
          className="list-item"
          key={run.id}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            paddingTop: 4,
            paddingBottom: 4,
          }}
        >
          <span className={ciPillClass(run.status)}>{run.status}</span>
          <span style={{ fontSize: 11, color: 'var(--text)', flex: 1 }}>{run.repo}</span>
          <span className="mono-small">{run.duration}</span>
          <span className="mono-small">{relativeTime(run.ranAt)}</span>
        </div>
      ))}
    </>
  );
}

export function DevPanel({ data = devMock, mode = 'expanded' }: DevPanelProps): ReactElement {
  return mode === 'compact' ? <DevCompact data={data} /> : <DevExpanded data={data} />;
}

export default DevPanel;
