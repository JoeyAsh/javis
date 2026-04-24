import { useState, type ReactElement } from 'react';
import { Tweaks, TWEAKS_DEFAULTS, useTweakApply } from '../../primitives/Tweaks';
import { Button } from '../../primitives/Button';
import type { TweaksState } from '../../primitives/Tweaks';

export function TweaksDemo(): ReactElement {
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

export default TweaksDemo;
