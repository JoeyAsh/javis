import { useState, type ReactElement } from 'react';
import { StatusDock } from '../../compositions/StatusDock';
import { TopBar } from '../../primitives/TopBar';
import { CssOrb } from '../../orb/CssOrb';
import { Panel } from '../../primitives/Panel';
import { BrandMark } from '../../primitives/BrandMark';
import { Button } from '../../primitives/Button';
import type { AppOrbState } from '@common/types';

export function HUDShellSection(): ReactElement {
    const [idle, setIdle] = useState(false);

    return (
        <section id="hud-shell" className="flex flex-col gap-4">
            <div>
                <h2 className="text-[12px] text-text font-mono mb-1">HUD Shell</h2>
                <p className="text-[10px] text-text-secondary font-mono">
                    Scene + Reactor + ViewportCorners + TopBar + Orb + StatusDock + panels
                </p>
            </div>

            <div className="flex items-center gap-2 mb-2">
                <Button
                    variant={idle ? 'primary' : 'ghost'}
                    size="sm"
                    onClick={() => setIdle((v) => !v)}
                >
                    idle mode {idle ? 'ON' : 'OFF'}
                </Button>
                <span className="text-[9px] text-text-muted font-mono">
                    (dims panels + fades topbar)
                </span>
            </div>

            {/* Scoped 1280×760 preview container */}
            <div
                className="border border-border rounded-[2px] overflow-hidden"
                style={{ position: 'relative', width: '100%', maxWidth: 1280, height: 760 }}
            >
                {/*
                  HUDShell is normally position:fixed so we render it inside a
                  relative container and override with a wrapper div to scope it.
                  The shell itself uses position:fixed/inset:0 — to preview it
                  inside the showcase we wrap in a scoped div that clips it.
                */}
                <div
                    style={{
                        position: 'absolute',
                        inset: 0,
                        overflow: 'hidden',
                    }}
                >
                    {/* We render the shell sub-elements manually scoped here */}
                    <ScopedHUDShellPreview idle={idle} onIdleToggle={() => setIdle((v) => !v)} />
                </div>
            </div>

            <p className="text-[9px] text-text-muted font-mono uppercase tracking-[1px]">
                Preview is clipped to section width. In production, HUDShell uses{' '}
                <span className="text-accent">position: fixed; inset: 0</span>.
            </p>
        </section>
    );
}

interface ScopedHUDShellPreviewProps {
    idle: boolean;
    onIdleToggle: () => void;
}

function ScopedHUDShellPreview({ idle, onIdleToggle }: ScopedHUDShellPreviewProps): ReactElement {
    const state: AppOrbState = 'idle';

    return (
        <div
            className={['hud-shell', idle && 'idle'].filter(Boolean).join(' ')}
            style={{ position: 'absolute', inset: 0 }}
        >
            {/* Scene (non-fixed so it fills the preview box) */}
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

            {/* Reactor scoped inside preview */}
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

            {/* TopBar — absolute inside preview */}
            <div style={{ position: 'absolute', top: 0, left: 0, right: 0, zIndex: 30 }}>
                <TopBar
                    left={<BrandMark />}
                    center={
                        <span className="text-[9px] text-text-secondary font-mono uppercase tracking-[2px]">
                            JARVIS · HUD SHELL PREVIEW
                        </span>
                    }
                    right={
                        <Button variant="ghost" size="sm" onClick={onIdleToggle}>
                            {idle ? 'EXIT IDLE' : 'IDLE'}
                        </Button>
                    }
                />
            </div>

            {/* Orb — centered */}
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

            {/* Sample panels */}
            <div className="hud-shell__children" style={{ position: 'absolute', inset: 0 }}>
                <div style={{ position: 'absolute', top: 56, left: 20, width: 200 }}>
                    <Panel title="SYSTEM">
                        <div className="text-[10px] text-text-secondary font-mono flex flex-col gap-1">
                            <span>CPU · 42%</span>
                            <span>MEM · 6.1 GB</span>
                            <span>UPTIME · 14h 22m</span>
                        </div>
                    </Panel>
                </div>
                <div style={{ position: 'absolute', top: 56, right: 20, width: 200 }}>
                    <Panel title="NOW PLAYING">
                        <div className="text-[10px] text-text-secondary font-mono flex flex-col gap-1">
                            <span className="text-text">Back in Black</span>
                            <span>AC/DC</span>
                        </div>
                    </Panel>
                </div>
            </div>

            {/* Status Dock — absolute bottom-center inside preview */}
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

            {/* Viewport corner marks scoped */}
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

export default HUDShellSection;
