import { useState, type ReactElement } from 'react';
import { StateSimulator } from '../../primitives/StateSimulator';
import { CssOrb } from '../../orb/CssOrb';
import { TweaksDemo } from './TweaksDemo';
import type { AppOrbState } from '@common/types';

export function DevOverlaysSection(): ReactElement {
    const [orbState, setOrbState] = useState<AppOrbState>('idle');

    return (
        <section id="dev-overlays" className="flex flex-col gap-6">
            <div>
                <h2 className="text-[12px] text-text font-mono mb-1">DEV OVERLAYS</h2>
                <p className="text-[10px] text-text-secondary font-mono">
                    StateSimulator · Tweaks + useTweakApply
                </p>
            </div>

            {/* StateSimulator inline */}
            <div className="flex flex-col gap-2">
                <span className="text-[9px] text-text-muted font-mono uppercase tracking-[1px]">
                    StateSimulator (position: inline)
                </span>
                <StateSimulator state={orbState} onChange={setOrbState} position="inline" />
            </div>

            {/* Live mini orb responding to state */}
            <div className="border border-border overflow-hidden relative h-[260px] bg-[rgba(5,5,8,0.95)]">
                <CssOrb state={orbState} particles />
            </div>

            <p className="text-[9px] text-text-muted font-mono uppercase tracking-[1px]">
                Orb reflects current simulated state. StateSimulator also available as{' '}
                <span className="text-accent">position: fixed-top</span> (see page top-bar area).
            </p>

            {/* Tweaks panel */}
            <TweaksDemo />
        </section>
    );
}

export default DevOverlaysSection;
