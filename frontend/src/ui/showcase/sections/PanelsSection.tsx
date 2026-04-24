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
                <span className="text-[9px] uppercase tracking-[2px] font-mono text-text-secondary">
                    TOPBAR
                </span>
                <TopBar
                    left={
                        <span className="text-[11px] text-text-secondary tracking-[1px]">
                            <span className="text-text">09:04:17</span>
                            &nbsp;·&nbsp;
                            <span>MONTAG, 21. APRIL 2026</span>
                            &nbsp;·&nbsp;
                            <span className="text-[var(--accent)]">● LINK · SECURE</span>
                        </span>
                    }
                    center={
                        <span className="text-[9px] tracking-[8px] text-text-muted uppercase font-mono">
                            J&nbsp;A&nbsp;R&nbsp;V&nbsp;I&nbsp;S&nbsp;/&nbsp;
                            <b className="text-[var(--accent-bright)] font-medium">MK XLII</b>
                        </span>
                    }
                    right={
                        <span className="text-[8px] tracking-[2px] text-text-muted uppercase font-mono">
                            N 48.21 · E 16.37
                        </span>
                    }
                />
                <p className="text-[9px] font-mono text-text-muted">
                    TopBar is fixed-position (top:10, left:10, right:10) — see page top for chrome
                    animation
                </p>
            </div>

            {/* Panel demos — fixed sizes to match handoff Sys panel dimensions */}
            <div className="flex flex-col gap-2">
                <span className="text-[9px] uppercase tracking-[2px] font-mono text-text-secondary">
                    PANEL SHELLS
                </span>
                <div className="flex flex-wrap gap-6 items-start">
                    {/* Panel at rest */}
                    <div className="flex flex-col gap-1.5">
                        <span className="text-[8px] tracking-[1px] text-text-muted uppercase font-mono">
                            AT REST
                        </span>
                        <Panel
                            title="Panel · Rest"
                            style={{ width: 316, height: 120 }}
                            focused={focusedId === 'rest'}
                            onFocus={() => setFocusedId('rest')}
                        >
                            <span className="text-[10px] text-text-secondary">
                                Hover to see brackets grow · click to focus
                            </span>
                        </Panel>
                    </div>

                    {/* Panel focused */}
                    <div className="flex flex-col gap-1.5">
                        <span className="text-[8px] tracking-[1px] text-text-muted uppercase font-mono">
                            FOCUSED
                        </span>
                        <Panel
                            title="Panel · Focused"
                            style={{ width: 316, height: 120 }}
                            focused={focusedId === 'focused' || focusedId === null}
                            onFocus={() => setFocusedId('focused')}
                        >
                            <span className="text-[10px] text-text">
                                Accent border · shimmer · bloom · cornerBreath active
                            </span>
                        </Panel>
                    </div>

                    {/* Panel with full header slots */}
                    <div className="flex flex-col gap-1.5">
                        <span className="text-[8px] tracking-[1px] text-text-muted uppercase font-mono">
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
                            <div className="grid grid-cols-2 gap-2.5">
                                {['CPU', 'RAM', 'GPU', 'TEMP', 'NET', 'DISK'].map((label) => (
                                    <div
                                        key={label}
                                        className="border border-[var(--border)] px-2 py-1.5"
                                    >
                                        <div className="text-[9px] text-text-secondary tracking-[1px] uppercase">
                                            {label}
                                        </div>
                                        <div className="text-[13px] text-[var(--accent-bright)] font-mono tabular-nums">
                                            42
                                            <small className="text-[9px] text-text-muted">%</small>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </Panel>
                    </div>

                    {/* Tall narrow panel */}
                    <div className="flex flex-col gap-1.5">
                        <span className="text-[8px] tracking-[1px] text-text-muted uppercase font-mono">
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
                            <div className="flex flex-col gap-2">
                                {(['User', 'JARVIS', 'User'] as const).map((role, i) => (
                                    <div
                                        key={i}
                                        className={`flex flex-col ${role === 'User' ? 'items-end' : 'items-start'}`}
                                    >
                                        <span className="text-[8px] text-text-muted tracking-[1px] uppercase font-mono">
                                            {role}
                                        </span>
                                        <span
                                            className={`text-[10px] ${role === 'JARVIS' ? 'text-text' : 'text-text-secondary'}`}
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
                    <div className="flex flex-col gap-1.5">
                        <span className="text-[8px] tracking-[1px] text-text-muted uppercase font-mono">
                            WIDE SHORT
                        </span>
                        <Panel
                            ix="♫"
                            title="Now Playing"
                            style={{ width: 480, height: 100 }}
                            focused={focusedId === 'nowplaying'}
                            onFocus={() => setFocusedId('nowplaying')}
                        >
                            <div className="flex items-center gap-3 h-full">
                                <div
                                    className="w-12 h-12 shrink-0 flex items-center justify-center text-[10px] text-[var(--bg)] font-bold tracking-[1px] shadow-[var(--glow)]"
                                    style={{
                                        background:
                                            'linear-gradient(135deg, #1a3a5c, #4ca8e8 55%, #6ec4ff)',
                                    }}
                                >
                                    AC/DC
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="text-[12px] text-text truncate">
                                        Thunderstruck
                                    </div>
                                    <div className="text-[10px] text-text-secondary">AC/DC</div>
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
