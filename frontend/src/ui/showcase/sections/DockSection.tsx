import { useState, type ReactElement } from 'react';
import { StatusDock } from '../../compositions/StatusDock';
import { Button } from '../../primitives/Button';
import type { AppOrbState } from '@common/types';

const STATES: AppOrbState[] = ['idle', 'listening', 'thinking', 'speaking', 'working'];

export function DockSection(): ReactElement {
    const [state, setState] = useState<AppOrbState>('idle');

    return (
        <section id="dock" className="flex flex-col gap-4">
            <div>
                <h2 className="text-[12px] text-text font-mono mb-1">Status Dock</h2>
                <p className="text-[10px] text-text-secondary font-mono">
                    WaveformMeter + PushToTalkButton + StatusLabel — fixed bottom-center
                </p>
            </div>

            {/* State selector */}
            <div className="flex flex-wrap items-center gap-2">
                {STATES.map((s) => (
                    <Button
                        key={s}
                        variant={state === s ? 'primary' : 'ghost'}
                        size="sm"
                        onClick={() => setState(s)}
                    >
                        {s}
                    </Button>
                ))}
            </div>

            <p className="text-[9px] text-text-muted font-mono uppercase tracking-[1px]">
                Dock renders at <span className="text-accent">position: fixed; bottom: 24px</span> —
                visible at page bottom.
            </p>

            {/* Live dock — renders at its natural fixed position */}
            <StatusDock
                state={state}
                onPTT={() => setState((s) => (s === 'idle' ? 'listening' : 'idle'))}
            />
        </section>
    );
}

export default DockSection;
