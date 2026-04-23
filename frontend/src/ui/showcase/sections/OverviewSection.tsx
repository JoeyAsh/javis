import { useState, type ReactElement } from 'react';
import { TopBar } from '../../primitives/TopBar';
import { BrandMark } from '../../primitives/BrandMark';
import { CssOrb } from '../../orb/CssOrb';
import { Panel } from '../../primitives/Panel';
import { StatusDock } from '../../compositions/StatusDock';
import { Label } from '../../primitives/Label';
import type { AppOrbState } from '@common/types';

export function OverviewSection(): ReactElement {
    const [state] = useState<AppOrbState>('idle');

    return (
        <section id="overview" className="flex flex-col gap-4">
            <div>
                <h2 className="text-[12px] text-text font-mono mb-1">OVERVIEW</h2>
                <p className="text-[10px] text-text-secondary font-mono leading-relaxed max-w-[700px]">
                    The JARVIS Component Library is a self-contained set of React/TypeScript
                    primitives and compositions designed to render the Hypermodern HUD visual
                    language. Every value — gradient stops, glow radii, animation curves, ring sizes
                    — is ported verbatim from the authoritative handoff prototype served at{' '}
                    <a
                        href="http://localhost:8899/JARVIS%20HUD%20Hypermodern.html"
                        target="_blank"
                        rel="noreferrer"
                        className="text-accent underline underline-offset-2"
                    >
                        localhost:8899
                    </a>
                    . No UI component library is used — all components are hand-built against the
                    design system tokens defined in <span className="text-accent">index.css</span>.
                </p>
            </div>

            {/* Full HUDShell preview at 1280×720 */}
            <div
                className="border border-border overflow-hidden"
                style={{ position: 'relative', width: '100%', maxWidth: 1280, height: 720 }}
            >
                <div style={{ position: 'absolute', inset: 0, overflow: 'hidden' }}>
                    <OverviewHUDPreview state={state} />
                </div>
            </div>

            <p className="text-[9px] text-text-muted font-mono uppercase tracking-[1px]">
                Full <span className="text-accent">HUDShell</span> composition — Scene · TopBar ·
                Orb · StatusDock · Window shells. In production uses{' '}
                <span className="text-accent">position: fixed; inset: 0</span>.
            </p>
        </section>
    );
}

interface OverviewHUDPreviewProps {
    state: AppOrbState;
}

function OverviewHUDPreview({ state }: OverviewHUDPreviewProps): ReactElement {
    return (
        <div style={{ position: 'absolute', inset: 0, background: 'var(--bg)' }}>
            {/* Scene layer */}
            <div
                className="lib-scene"
                style={{ position: 'absolute', inset: 0 }}
                aria-hidden="true"
            >
                <div className="lib-scene__grid" />
                <div className="lib-scene__scanlines" />
                <div className="lib-scene__vignette" />
                <div className="lib-scene__noise" />
                <div className="lib-scene__horizon" />
            </div>

            {/* Reactor */}
            <div
                className="lib-reactor"
                style={{
                    position: 'absolute',
                    bottom: -360,
                    left: '50%',
                    transform: 'translateX(-50%)',
                }}
                aria-hidden="true"
            />

            {/* TopBar */}
            <div style={{ position: 'absolute', top: 0, left: 0, right: 0, zIndex: 30 }}>
                <TopBar
                    left={<BrandMark />}
                    center={
                        <span className="text-[9px] text-text-secondary font-mono uppercase tracking-[2px]">
                            JARVIS · HUD PREVIEW
                        </span>
                    }
                    right={
                        <span className="text-[8px] text-text-muted font-mono uppercase tracking-[1px]">
                            N 48.21 · E 16.37
                        </span>
                    }
                />
            </div>

            {/* Orb centered */}
            <div
                style={{
                    position: 'absolute',
                    inset: 0,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    zIndex: 0,
                    pointerEvents: 'none',
                }}
            >
                <CssOrb state={state} particles />
            </div>

            {/* Window shells */}
            <div style={{ position: 'absolute', top: 56, left: 20, width: 220, zIndex: 10 }}>
                <Panel title="SYSTEM" ix="◈">
                    <Label dim>CPU · RAM · UPTIME</Label>
                </Panel>
            </div>
            <div style={{ position: 'absolute', top: 56, right: 20, width: 220, zIndex: 10 }}>
                <Panel title="TRANSCRIPT" ix="▸">
                    <Label dim>Awaiting input...</Label>
                </Panel>
            </div>
            <div style={{ position: 'absolute', bottom: 80, left: 20, width: 220, zIndex: 10 }}>
                <Panel title="AGENDA" ix="▦">
                    <Label dim>No events</Label>
                </Panel>
            </div>

            {/* Status Dock */}
            <div
                style={{
                    position: 'absolute',
                    left: '50%',
                    bottom: 24,
                    transform: 'translateX(-50%)',
                    zIndex: 25,
                }}
            >
                <StatusDock state={state} />
            </div>

            {/* Viewport corners */}
            {(['tl', 'tr', 'bl', 'br'] as const).map((pos) => (
                <span
                    key={pos}
                    className={`lib-viewport-corner ${pos}`}
                    style={{ position: 'absolute' }}
                    aria-hidden="true"
                />
            ))}
        </div>
    );
}

export default OverviewSection;
