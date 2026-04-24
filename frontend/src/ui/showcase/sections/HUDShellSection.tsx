import { useState, type ReactElement } from 'react';
import { Button } from '../../primitives/Button';
import { ScopedHUDShellPreview } from './ScopedHUDShellPreview';

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
                className="border border-border rounded-[2px] overflow-hidden relative w-full max-w-[1280px] h-[760px]"
            >
                {/*
                  HUDShell is normally position:fixed so we render it inside a
                  relative container and override with a wrapper div to scope it.
                  The shell itself uses position:fixed/inset:0 — to preview it
                  inside the showcase we wrap in a scoped div that clips it.
                */}
                <div className="absolute inset-0 overflow-hidden">
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

export default HUDShellSection;
