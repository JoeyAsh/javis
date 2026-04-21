import type { ReactElement } from 'react';
import { selfFixMock } from '../../mock/selfFixMock';
import type { SelfFixEntry, PanelMode } from '../../types';

export interface SelfFixPanelProps {
    entries?: SelfFixEntry[];
    mode?: PanelMode;
}

function relativeTime(iso: string): string {
    const diff = Date.now() - new Date(iso).getTime();
    const secs = Math.floor(diff / 1000);
    if (secs < 60) return `${secs}s ago`;
    const mins = Math.floor(secs / 60);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    return `${hrs}h ago`;
}

function SelfFixCompact({ entries }: { entries: SelfFixEntry[] }): ReactElement {
    const active = entries.find((e) => e.status === 'in_progress');
    if (!active) {
        return (
            <div className="window-compact-row" style={{ color: 'var(--text-muted)' }}>
                Keine Fixes aktiv
            </div>
        );
    }
    return (
        <div className="window-compact-row" style={{ gap: 6 }}>
            <span className="pulse-dot" aria-hidden />
            <span className="mono-small" style={{ color: 'var(--warning)', flexShrink: 0 }}>
                Fix läuft
            </span>
            <span
                className="truncate"
                style={{ fontSize: 12, color: 'var(--text)', flex: 1 }}
                title={active.summary}
            >
                {active.summary}
            </span>
        </div>
    );
}

function SelfFixExpanded({ entries }: { entries: SelfFixEntry[] }): ReactElement {
    return (
        <>
            {entries.map((e) => {
                const isInProgress = e.status === 'in_progress';
                return (
                    <div
                        className="list-item"
                        key={e.id}
                        style={{
                            borderLeft: `2px solid ${isInProgress ? 'var(--warning)' : 'var(--success)'}`,
                            paddingLeft: 10,
                            marginBottom: 8,
                        }}
                    >
                        <div
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 6,
                                marginBottom: 4,
                            }}
                        >
                            {isInProgress && <span className="pulse-dot" aria-hidden />}
                            <span
                                style={{
                                    fontSize: 12,
                                    color: isInProgress ? 'var(--warning)' : 'var(--success)',
                                    fontWeight: 500,
                                    flex: 1,
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    whiteSpace: 'nowrap',
                                }}
                            >
                                {e.summary}
                            </span>
                            <span className="mono-small">{relativeTime(e.startedAt)}</span>
                        </div>
                        <div
                            style={{
                                fontSize: 10,
                                color: 'var(--text-secondary)',
                                lineHeight: 1.4,
                                marginBottom: 6,
                            }}
                        >
                            {e.detail}
                        </div>

                        {e.status === 'completed' && (
                            <>
                                <div
                                    style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: 8,
                                        marginBottom: 6,
                                        fontSize: 10,
                                    }}
                                >
                                    <span
                                        style={{
                                            fontFamily: 'var(--font)',
                                            color: 'var(--accent-bright)',
                                            background: 'rgba(76,168,232,0.08)',
                                            padding: '1px 4px',
                                            letterSpacing: 1,
                                        }}
                                    >
                                        {e.commitSha ?? '——'}
                                    </span>
                                    {e.added !== undefined && (
                                        <span style={{ color: 'var(--success)' }}>+{e.added}</span>
                                    )}
                                    {e.removed !== undefined && (
                                        <span style={{ color: 'var(--danger)' }}>-{e.removed}</span>
                                    )}
                                </div>
                                <div style={{ display: 'flex', gap: 6 }} data-no-drag>
                                    <button
                                        type="button"
                                        className="hud-iconbtn"
                                        style={{ width: 'auto', padding: '0 10px' }}
                                    >
                                        ACCEPT
                                    </button>
                                    <button
                                        type="button"
                                        className="hud-iconbtn"
                                        style={{
                                            width: 'auto',
                                            padding: '0 10px',
                                            color: 'var(--danger)',
                                        }}
                                    >
                                        DISCARD
                                    </button>
                                </div>
                            </>
                        )}
                    </div>
                );
            })}
        </>
    );
}

export function SelfFixPanel({
    entries = selfFixMock,
    mode = 'expanded',
}: SelfFixPanelProps): ReactElement {
    return mode === 'compact' ? (
        <SelfFixCompact entries={entries} />
    ) : (
        <SelfFixExpanded entries={entries} />
    );
}

export default SelfFixPanel;
