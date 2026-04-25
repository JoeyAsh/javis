import { useState, type ReactElement } from 'react';
import { GlassCard } from '../../compositions/GlassCard';
import { StatusBadge } from '../../compositions/StatusBadge';
import { Panel } from '../../primitives/Panel';
import { TopBar } from '../../primitives/TopBar';
import { BrandMark } from '../../primitives/BrandMark';
import { Button } from '../../primitives/Button';
import { StatusDock } from '../../compositions/StatusDock';
import { ShowcaseCard } from '../ShowcaseCard';
import type { AppOrbState } from '@common/types';

const STATES: AppOrbState[] = ['idle', 'listening', 'thinking', 'speaking', 'working'];

export function CompositionsSection(): ReactElement {
    const [dockState, setDockState] = useState<AppOrbState>('idle');
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
                <div className="flex flex-wrap gap-6 items-start">
                    <div className="flex flex-col gap-[6px]">
                        <span className="text-[8px] tracking-[1px] text-text-muted font-mono uppercase">
                            AT REST
                        </span>
                        <Panel
                            title="Panel · Rest"
                            style={{ width: 280, height: 100 } as React.CSSProperties}
                            focused={focusedId === 'rest'}
                            onFocus={() => setFocusedId('rest')}
                        >
                            <span className="text-[10px] text-text-secondary font-mono">
                                Hover → brackets grow · click → focus
                            </span>
                        </Panel>
                    </div>

                    <div className="flex flex-col gap-[6px]">
                        <span className="text-[8px] tracking-[1px] text-text-muted font-mono uppercase">
                            FOCUSED
                        </span>
                        <Panel
                            title="Panel · Focused"
                            style={{ width: 280, height: 100 } as React.CSSProperties}
                            focused={focusedId === 'focused' || focusedId === null}
                            onFocus={() => setFocusedId('focused')}
                        >
                            <span className="text-[10px] text-text font-mono">
                                Accent border · shimmer · bloom · cornerBreath active
                            </span>
                        </Panel>
                    </div>

                    <div className="flex flex-col gap-[6px]">
                        <span className="text-[8px] tracking-[1px] text-text-muted font-mono uppercase">
                            FULL HEADER
                        </span>
                        <Panel
                            ix="◈"
                            title="System Vitals · live"
                            badge="LIVE"
                            style={{ width: 280, height: 180 } as React.CSSProperties}
                            focused={focusedId === 'vitals'}
                            onFocus={() => setFocusedId('vitals')}
                        >
                            <div className="grid grid-cols-2 gap-2">
                                {['CPU', 'RAM', 'GPU', 'TEMP'].map((label) => (
                                    <div
                                        key={label}
                                        className="border border-border px-2 py-1"
                                    >
                                        <div className="text-[9px] text-text-secondary font-mono uppercase tracking-[1px]">
                                            {label}
                                        </div>
                                        <div className="text-[13px] text-accent-bright font-mono tabular-nums">
                                            42
                                            <small className="text-[9px] text-text-muted">
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
                        <span className="text-[11px] text-text-secondary font-mono tracking-[1px]">
                            <span className="text-text">09:04:17</span>
                            &nbsp;·&nbsp;
                            <span className="text-accent">● LINK · SECURE</span>
                        </span>
                    }
                    center={
                        <span className="text-[9px] tracking-[8px] text-text-muted font-mono uppercase">
                            J&nbsp;A&nbsp;R&nbsp;V&nbsp;I&nbsp;S&nbsp;/&nbsp;
                            <b className="text-accent-bright font-medium">
                                MK XLII
                            </b>
                        </span>
                    }
                    right={<BrandMark />}
                />
                <p className="text-[9px] font-mono text-text-muted">
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
                <p className="text-[9px] font-mono text-text-muted">
                    Dock renders at{' '}
                    <span className="text-accent">position: fixed; bottom: 24px</span> —
                    visible at page bottom.
                </p>
            </div>
        </section>
    );
}

export default CompositionsSection;
