import { useState, type ReactElement } from 'react';
import { Panel } from '../../primitives/Panel';
import { TopBar } from '../../primitives/TopBar';

export function PanelsSection(): ReactElement {
    const [focusedId, setFocusedId] = useState<string | null>(null);

    return (
        <section id="panels" className="flex flex-col gap-8">
            <div>
                <h2 className="text-[12px] text-text font-mono mb-1">Panels</h2>
                <p className="text-[10px] text-text-secondary font-mono">
                    Panel chrome shell — corner brackets · trace · bloom · rails · header slots
                </p>
            </div>

            {/* TopBar smoke test — rendered live at page top via fixed positioning */}
            <div className="flex flex-col gap-2">
                <span
                    className="text-[9px] uppercase tracking-[2px] font-mono"
                    style={{ color: 'var(--text-secondary)' }}
                >
                    TOPBAR
                </span>
                <TopBar
                    left={
                        <span
                            style={{
                                fontSize: 11,
                                color: 'var(--text-secondary)',
                                letterSpacing: 1,
                            }}
                        >
                            <span style={{ color: 'var(--text)' }}>09:04:17</span>
                            &nbsp;·&nbsp;
                            <span>MONTAG, 21. APRIL 2026</span>
                            &nbsp;·&nbsp;
                            <span style={{ color: 'var(--accent)' }}>● LINK · SECURE</span>
                        </span>
                    }
                    center={
                        <span
                            style={{
                                fontSize: 9,
                                letterSpacing: 8,
                                color: 'var(--text-muted)',
                                textTransform: 'uppercase',
                            }}
                        >
                            J&nbsp;A&nbsp;R&nbsp;V&nbsp;I&nbsp;S&nbsp;/&nbsp;
                            <b style={{ color: 'var(--accent-bright)', fontWeight: 500 }}>
                                MK XLII
                            </b>
                        </span>
                    }
                    right={
                        <span
                            style={{
                                fontSize: 8,
                                letterSpacing: 2,
                                color: 'var(--text-muted)',
                                textTransform: 'uppercase',
                            }}
                        >
                            N 48.21 · E 16.37
                        </span>
                    }
                />
                <p className="text-[9px] font-mono" style={{ color: 'var(--text-muted)' }}>
                    TopBar is fixed-position (top:10, left:10, right:10) — see page top for chrome
                    animation
                </p>
            </div>

            {/* Panel demos — fixed sizes to match handoff Sys panel dimensions */}
            <div className="flex flex-col gap-2">
                <span
                    className="text-[9px] uppercase tracking-[2px] font-mono"
                    style={{ color: 'var(--text-secondary)' }}
                >
                    PANEL SHELLS
                </span>
                <div
                    style={{
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: 24,
                        alignItems: 'flex-start',
                    }}
                >
                    {/* Panel at rest */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        <span
                            style={{
                                fontSize: 8,
                                letterSpacing: 1,
                                color: 'var(--text-muted)',
                                textTransform: 'uppercase',
                            }}
                        >
                            AT REST
                        </span>
                        <Panel
                            title="Panel · Rest"
                            style={{ width: 316, height: 120 }}
                            focused={focusedId === 'rest'}
                            onFocus={() => setFocusedId('rest')}
                        >
                            <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
                                Hover to see brackets grow · click to focus
                            </span>
                        </Panel>
                    </div>

                    {/* Panel focused */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        <span
                            style={{
                                fontSize: 8,
                                letterSpacing: 1,
                                color: 'var(--text-muted)',
                                textTransform: 'uppercase',
                            }}
                        >
                            FOCUSED
                        </span>
                        <Panel
                            title="Panel · Focused"
                            style={{ width: 316, height: 120 }}
                            focused={focusedId === 'focused' || focusedId === null}
                            onFocus={() => setFocusedId('focused')}
                        >
                            <span style={{ fontSize: 10, color: 'var(--text)' }}>
                                Accent border · shimmer · bloom · cornerBreath active
                            </span>
                        </Panel>
                    </div>

                    {/* Panel with full header slots */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        <span
                            style={{
                                fontSize: 8,
                                letterSpacing: 1,
                                color: 'var(--text-muted)',
                                textTransform: 'uppercase',
                            }}
                        >
                            FULL HEADER
                        </span>
                        <Panel
                            ix="◈"
                            title="System Vitals · live"
                            badge="LIVE"
                            style={{ width: 316, height: 300 }}
                            focused={focusedId === 'vitals'}
                            onFocus={() => setFocusedId('vitals')}
                        >
                            <div
                                style={{
                                    display: 'grid',
                                    gridTemplateColumns: 'repeat(2, 1fr)',
                                    gap: 10,
                                }}
                            >
                                {['CPU', 'RAM', 'GPU', 'TEMP', 'NET', 'DISK'].map((label) => (
                                    <div
                                        key={label}
                                        style={{
                                            border: '1px solid var(--border)',
                                            padding: '6px 8px',
                                        }}
                                    >
                                        <div
                                            style={{
                                                fontSize: 9,
                                                color: 'var(--text-secondary)',
                                                letterSpacing: 1,
                                                textTransform: 'uppercase',
                                            }}
                                        >
                                            {label}
                                        </div>
                                        <div
                                            style={{
                                                fontSize: 13,
                                                color: 'var(--accent-bright)',
                                                fontVariantNumeric: 'tabular-nums',
                                            }}
                                        >
                                            42
                                            <small
                                                style={{
                                                    fontSize: 9,
                                                    color: 'var(--text-muted)',
                                                }}
                                            >
                                                %
                                            </small>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </Panel>
                    </div>

                    {/* Tall narrow panel */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        <span
                            style={{
                                fontSize: 8,
                                letterSpacing: 1,
                                color: 'var(--text-muted)',
                                textTransform: 'uppercase',
                            }}
                        >
                            TALL NARROW
                        </span>
                        <Panel
                            ix="▸"
                            title="Transcript"
                            badge="INBOX"
                            style={{ width: 200, height: 340 }}
                            focused={focusedId === 'transcript'}
                            onFocus={() => setFocusedId('transcript')}
                        >
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                {['User', 'JARVIS', 'User'].map((role, i) => (
                                    <div
                                        key={i}
                                        style={{
                                            display: 'flex',
                                            flexDirection: 'column',
                                            alignItems: role === 'User' ? 'flex-end' : 'flex-start',
                                        }}
                                    >
                                        <span
                                            style={{
                                                fontSize: 8,
                                                color: 'var(--text-muted)',
                                                letterSpacing: 1,
                                                textTransform: 'uppercase',
                                            }}
                                        >
                                            {role}
                                        </span>
                                        <span
                                            style={{
                                                fontSize: 10,
                                                color:
                                                    role === 'User'
                                                        ? 'var(--text-secondary)'
                                                        : 'var(--text)',
                                            }}
                                        >
                                            {role === 'JARVIS'
                                                ? 'Understood. Executing…'
                                                : 'Hello JARVIS.'}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </Panel>
                    </div>

                    {/* Wide short panel */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        <span
                            style={{
                                fontSize: 8,
                                letterSpacing: 1,
                                color: 'var(--text-muted)',
                                textTransform: 'uppercase',
                            }}
                        >
                            WIDE SHORT
                        </span>
                        <Panel
                            ix="♫"
                            title="Now Playing"
                            style={{ width: 480, height: 100 }}
                            focused={focusedId === 'nowplaying'}
                            onFocus={() => setFocusedId('nowplaying')}
                        >
                            <div
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 12,
                                    height: '100%',
                                }}
                            >
                                <div
                                    style={{
                                        width: 48,
                                        height: 48,
                                        background:
                                            'linear-gradient(135deg, #1a3a5c, #4ca8e8 55%, #6ec4ff)',
                                        flexShrink: 0,
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        fontSize: 10,
                                        color: 'var(--bg)',
                                        fontWeight: 700,
                                        letterSpacing: 1,
                                        boxShadow: 'var(--glow)',
                                    }}
                                >
                                    AC/DC
                                </div>
                                <div style={{ flex: 1, minWidth: 0 }}>
                                    <div
                                        style={{
                                            fontSize: 12,
                                            color: 'var(--text)',
                                            overflow: 'hidden',
                                            textOverflow: 'ellipsis',
                                            whiteSpace: 'nowrap',
                                        }}
                                    >
                                        Thunderstruck
                                    </div>
                                    <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
                                        AC/DC
                                    </div>
                                </div>
                            </div>
                        </Panel>
                    </div>
                </div>
            </div>
        </section>
    );
}

export default PanelsSection;
