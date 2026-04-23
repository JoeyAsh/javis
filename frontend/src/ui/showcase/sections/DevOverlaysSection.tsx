import { useState, type ReactElement } from 'react';
import { StateSimulator } from '../../primitives/StateSimulator';
import { Tweaks, TWEAKS_DEFAULTS, useTweakApply } from '../../primitives/Tweaks';
import { Button } from '../../primitives/Button';
import { CssOrb } from '../../orb/CssOrb';
import type { AppOrbState } from '@common/types';
import type { TweaksState } from '../../primitives/Tweaks';

function TweaksDemo(): ReactElement {
    const [tweaks, setTweaks] = useState<TweaksState>(TWEAKS_DEFAULTS);
    const [tweaksOpen, setTweaksOpen] = useState(false);
    useTweakApply(tweaks);

    return (
        <div className="flex flex-col gap-3">
            <div className="flex items-center gap-2">
                <Button
                    variant={tweaksOpen ? 'primary' : 'ghost'}
                    size="sm"
                    onClick={() => setTweaksOpen((v) => !v)}
                >
                    {tweaksOpen ? 'CLOSE TWEAKS' : 'OPEN TWEAKS'}
                </Button>
                <span className="text-[9px] text-text-muted font-mono uppercase tracking-[1px]">
                    hue: {tweaks.hue}° · glow: {tweaks.glow}
                </span>
            </div>
            <p className="text-[9px] text-text-muted font-mono uppercase tracking-[1px]">
                Tweaks panel renders at{' '}
                <span className="text-accent">position: fixed; bottom: 110px; right: 14px</span>.
                Moving the hue slider recolors the live mini-orb below.
            </p>
            <Tweaks open={tweaksOpen} tweaks={tweaks} onChange={setTweaks} />
        </div>
    );
}

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
            <div
                className="border border-border overflow-hidden"
                style={{ position: 'relative', height: '260px', background: 'rgba(5,5,8,0.95)' }}
            >
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
