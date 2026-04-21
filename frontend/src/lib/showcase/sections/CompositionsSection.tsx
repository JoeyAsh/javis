import { useState, type ReactElement } from 'react';
import { GlassCard } from '../../compositions/GlassCard';
import { StatusBadge } from '../../compositions/StatusBadge';
import { Panel } from '../../primitives/Panel';
import { TopBar } from '../../primitives/TopBar';
import { BrandMark } from '../../primitives/BrandMark';
import { Button } from '../../primitives/Button';
import { StatusDock } from '../../compositions/StatusDock';
import { ShowcaseCard } from '../ShowcaseCard';
import type { OrbState } from '../../primitives/Orb/Orb';

const STATES: OrbState[] = ['idle', 'listening', 'thinking', 'speaking', 'working'];

export function CompositionsSection(): ReactElement {
    const [dockState, setDockState] = useState<OrbState>('idle');
    const [focusedId, setFocusedId] = useState<string | null>(null);

    return (
        <section id="compositions" className="flex flex-col gap-8">
            <div>
                <h2 className="text-[12px] text-text font-mono mb-1">COMPOSITIONS</h2>
                <p className="text-[10px] text-text-secondary font-mono">
                    GlassCard · StatusBadge · Panel · TopBar · StatusDock
                </p>
            </div>

            {/* GlassCard */}
            <div className="flex flex-col gap-3">
                <span className="text-[9px] uppercase tracking-[2px] font-mono text-text-secondary">
                    GlassCard
                </span>
                <div className="grid grid-cols-2 gap-3">
                    <ShowcaseCard
                        label="GLASS CARD DEFAULT"
                        code={`<GlassCard title="SYSTEM">\n  …\n</GlassCard>`}
                    >
                        <GlassCard title="SYSTEM">
                            <span className="text-[10px] text-text-secondary font-mono">
                                CPU · 42%
                            </span>
                        </GlassCard>
                    </ShowcaseCard>
                    <ShowcaseCard
                        label="GLASS CARD FOCUSED"
                        code={`<GlassCard title="FOCUSED" focused>\n  …\n</GlassCard>`}
                    >
                        <GlassCard title="FOCUSED" focused>
                            <span className="text-[10px] text-accent font-mono">
                                Active · cornerBreath · bloom
                            </span>
                        </GlassCard>
                    </ShowcaseCard>
                </div>
            </div>

            {/* StatusBadge */}
            <div className="flex flex-col gap-3">
                <span className="text-[9px] uppercase tracking-[2px] font-mono text-text-secondary">
                    StatusBadge
                </span>
                <ShowcaseCard
                    label="STATUS BADGE VARIANTS"
                    code={`<StatusBadge state="online" label="LINK · SECURE" />`}
                >
                    <div className="flex flex-wrap gap-4 justify-center">
                        <StatusBadge state="online" label="LINK · SECURE" pulse />
                        <StatusBadge state="warn" label="DEGRADED" />
                        <StatusBadge state="offline" label="OFFLINE" />
                    </div>
                </ShowcaseCard>
            </div>

            {/* Panel shells */}
            <div className="flex flex-col gap-3">
                <span className="text-[9px] uppercase tracking-[2px] font-mono text-text-secondary">
                    Panel
                </span>
                <div
                    style={{
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: 24,
                        alignItems: 'flex-start',
                    }}
                >
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
                            style={{ width: 280, height: 100 }}
                            focused={focusedId === 'rest'}
                            onFocus={() => setFocusedId('rest')}
                        >
                            <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
                                Hover → brackets grow · click → focus
                            </span>
                        </Panel>
                    </div>

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
                            style={{ width: 280, height: 100 }}
                            focused={focusedId === 'focused' || focusedId === null}
                            onFocus={() => setFocusedId('focused')}
                        >
                            <span style={{ fontSize: 10, color: 'var(--text)' }}>
                                Accent border · shimmer · bloom · cornerBreath active
                            </span>
                        </Panel>
                    </div>

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
                            style={{ width: 280, height: 180 }}
                            focused={focusedId === 'vitals'}
                            onFocus={() => setFocusedId('vitals')}
                        >
                            <div
                                style={{
                                    display: 'grid',
                                    gridTemplateColumns: 'repeat(2, 1fr)',
                                    gap: 8,
                                }}
                            >
                                {['CPU', 'RAM', 'GPU', 'TEMP'].map((label) => (
                                    <div
                                        key={label}
                                        style={{
                                            border: '1px solid var(--border)',
                                            padding: '4px 8px',
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
                                                style={{ fontSize: 9, color: 'var(--text-muted)' }}
                                            >
                                                %
                                            </small>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </Panel>
                    </div>
                </div>
            </div>

            {/* TopBar */}
            <div className="flex flex-col gap-3">
                <span className="text-[9px] uppercase tracking-[2px] font-mono text-text-secondary">
                    TopBar (fixed-position — see page top)
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
                    right={<BrandMark />}
                />
                <p className="text-[9px] font-mono" style={{ color: 'var(--text-muted)' }}>
                    TopBar is fixed-position (top:10, left:10, right:10) — see page top for animated
                    corner brackets + circumnavigating trace.
                </p>
            </div>

            {/* StatusDock */}
            <div className="flex flex-col gap-3">
                <span className="text-[9px] uppercase tracking-[2px] font-mono text-text-secondary">
                    StatusDock (fixed bottom-center — see page bottom)
                </span>
                <div className="flex flex-wrap items-center gap-2 mb-2">
                    {STATES.map((s) => (
                        <Button
                            key={s}
                            variant={dockState === s ? 'primary' : 'ghost'}
                            size="sm"
                            onClick={() => setDockState(s)}
                        >
                            {s}
                        </Button>
                    ))}
                </div>
                <StatusDock
                    state={dockState}
                    onPTT={() => setDockState((s) => (s === 'idle' ? 'listening' : 'idle'))}
                />
                <p className="text-[9px] font-mono" style={{ color: 'var(--text-muted)' }}>
                    Dock renders at{' '}
                    <span style={{ color: 'var(--accent)' }}>position: fixed; bottom: 24px</span> —
                    visible at page bottom.
                </p>
            </div>
        </section>
    );
}

export default CompositionsSection;
