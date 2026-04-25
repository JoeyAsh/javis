import { useState, useEffect, type ReactElement } from 'react';
import { PushToTalkButton } from '../../primitives/PushToTalkButton';
import { WaveformMeter } from '../../primitives/WaveformMeter';
import { WaveStrip } from '../../primitives/WaveStrip';
import { StatusLabel } from '../../primitives/StatusLabel';
import { Hint } from '../../primitives/Hint';
import { ShowcaseCard } from '../ShowcaseCard';
import type { AppOrbState } from '@common/types';

const STATES: AppOrbState[] = ['idle', 'listening', 'thinking', 'speaking', 'working'];

export function ChromeInteractiveSection(): ReactElement {
    const [pttActive, setPttActive] = useState(false);
    const [cycledState, setCycledState] = useState<AppOrbState>('idle');

    // Cycle through states for StatusLabel demo
    useEffect(() => {
        let i = 0;
        const id = setInterval(() => {
            i = (i + 1) % STATES.length;
            setCycledState(STATES[i]);
        }, 1800);
        return () => clearInterval(id);
    }, []);

    return (
        <section id="chrome-interactive" className="flex flex-col gap-4">
            <div>
                <h2 className="text-[12px] text-text font-mono mb-1">Chrome — Interactive</h2>
                <p className="text-[10px] text-text-secondary font-mono">
                    PushToTalkButton · WaveformMeter · WaveStrip · StatusLabel · Hint
                </p>
            </div>
            <div className="grid grid-cols-3 gap-3">
                {/* PTT idle */}
                <ShowcaseCard label="PTT IDLE" code={`<PushToTalkButton />`} dark>
                    <PushToTalkButton />
                </ShowcaseCard>

                {/* PTT active */}
                <ShowcaseCard
                    label="PTT ACTIVE (click to toggle)"
                    code={`<PushToTalkButton active onClick={handler} />`}
                    dark
                >
                    <PushToTalkButton active={pttActive} onClick={() => setPttActive((v) => !v)} />
                </ShowcaseCard>

                {/* Waveform meter active */}
                <ShowcaseCard label="WAVEFORM METER ACTIVE" code={`<WaveformMeter active />`} dark>
                    <WaveformMeter active />
                </ShowcaseCard>

                {/* Waveform meter inactive */}
                <ShowcaseCard
                    label="WAVEFORM METER INACTIVE"
                    code={`<WaveformMeter active={false} />`}
                    dark
                >
                    <WaveformMeter active={false} />
                </ShowcaseCard>

                {/* Waveform meter mirrored */}
                <ShowcaseCard
                    label="WAVEFORM METER MIRRORED"
                    code={`<WaveformMeter active mirrored />`}
                    dark
                >
                    <WaveformMeter active mirrored />
                </ShowcaseCard>

                {/* WaveStrip */}
                <ShowcaseCard label="WAVE STRIP" code={`<WaveStrip active />`} dark>
                    <div className="flex flex-col gap-3 items-center">
                        <div className="flex items-center gap-2 text-[10px] text-text-secondary font-mono">
                            <WaveStrip active />
                            <span>Now Playing</span>
                            <WaveStrip active mirrored />
                        </div>
                        <div className="flex items-center gap-2 text-[10px] text-text-muted font-mono">
                            <WaveStrip active={false} />
                            <span>inactive</span>
                        </div>
                    </div>
                </ShowcaseCard>

                {/* StatusLabel cycling */}
                <ShowcaseCard
                    label="STATUS LABEL (auto-cycling)"
                    code={`<StatusLabel state={state} />`}
                    dark
                >
                    <StatusLabel state={cycledState} />
                </ShowcaseCard>

                {/* Hint */}
                <ShowcaseCard
                    label="HINT (inline variant)"
                    code={`<Hint position="inline">\n  PUSH TO TALK · <Hint.Key>SPACE</Hint.Key>\n</Hint>`}
                    dark
                >
                    <Hint position="inline">
                        PUSH TO TALK &middot; <Hint.Key>SPACE</Hint.Key>&nbsp;&nbsp;IDLE &middot;{' '}
                        <Hint.Key>CTRL+.</Hint.Key>
                    </Hint>
                </ShowcaseCard>
            </div>
        </section>
    );
}

export default ChromeInteractiveSection;
