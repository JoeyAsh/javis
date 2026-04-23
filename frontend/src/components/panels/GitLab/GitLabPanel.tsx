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
import type { GitLabStatePayload, PanelMode } from '../../../types';
import { usePanelAvailable } from '../../hud/PanelAvailability';
import { PipelineRow } from './PipelineRow';
import './GitLabPanel.css';

export interface GitLabPanelProps {
    mode?: PanelMode;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

type PipelineStatus =
    | 'success'
    | 'failed'
    | 'running'
    | 'pending'
    | 'canceled'
    | 'skipped'
    | string;

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
                    <span
                        className="gitlab-compact__count"
                        style={{ color: 'var(--accent-bright)' }}
                    >
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
            {data.error !== null && <div className="gitlab-error">{data.error}</div>}
            {data.pipelines.slice(0, 3).map((p) => (
                <PipelineRow key={p.project} pipeline={p} />
            ))}
            {data.pipelines.length === 0 && data.error === null && (
                <div className="gitlab-empty">Keine aktiven Pipelines</div>
            )}
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
 * Returns null if no backend payload arrives within the availability timeout.
 */
export function GitLabPanel({ mode = 'expanded' }: GitLabPanelProps): ReactElement {
    const { data, available } = useGitlabState();

    // Report availability up to HudWindows.
    usePanelAvailable('gitlab', available || data !== null);

    // Backend not available — show fallback message.
    if (!available && data === null) {
        return mode === 'compact' ? (
            <div className="gitlab-compact">
                <span className="gitlab-loading">GitLab momentan nicht erreichbar</span>
            </div>
        ) : (
            <div className="gitlab-panel">
                <span className="gitlab-loading">GitLab momentan nicht erreichbar</span>
            </div>
        );
    }

    return mode === 'compact' ? <GitLabCompact data={data} /> : <GitLabExpanded data={data} />;
}

export default GitLabPanel;
