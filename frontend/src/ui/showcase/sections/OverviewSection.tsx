import { useState, type ReactElement } from 'react';
import type { AppOrbState } from '@common/types';
import { OverviewHUDPreview } from './OverviewHUDPreview';

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
            <div className="border border-border overflow-hidden relative w-full max-w-[1280px] h-[720px]">
                <div className="absolute inset-0 overflow-hidden">
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

export default OverviewSection;
