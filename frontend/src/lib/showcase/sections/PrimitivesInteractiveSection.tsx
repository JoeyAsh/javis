import { useState, useEffect, type ReactElement } from 'react';
import { PushToTalkButton } from '../../primitives/PushToTalkButton';
import { WaveformMeter } from '../../primitives/WaveformMeter';
import { WaveStrip } from '../../primitives/WaveStrip';
import { StatusLabel } from '../../primitives/StatusLabel';
import { Hint } from '../../primitives/Hint';
import { ShowcaseCard } from '../ShowcaseCard';
import type { OrbState } from '../../primitives/Orb/Orb';

const STATES: OrbState[] = ['idle', 'listening', 'thinking', 'speaking', 'working'];

export function PrimitivesInteractiveSection(): ReactElement {
    const [pttActive, setPttActive] = useState(false);
    const [cycledState, setCycledState] = useState<OrbState>('idle');

    useEffect(() => {
        let i = 0;
        const id = setInterval(() => {
            i = (i + 1) % STATES.length;
            setCycledState(STATES[i]);
        }, 1800);
        return () => clearInterval(id);
    }, []);

    return (
        <section id="primitives-interactive" className="flex flex-col gap-4">
            <div>
                <h2 className="text-[12px] text-text font-mono mb-1">PRIMITIVES — Interactive</h2>
                <p className="text-[10px] text-text-secondary font-mono">
                    PushToTalkButton · WaveformMeter · WaveStrip · StatusLabel · Hint
                </p>
            </div>
            <div className="grid grid-cols-3 gap-3">
                <ShowcaseCard label="PTT IDLE" code={`<PushToTalkButton />`} dark>
                    <PushToTalkButton />
                </ShowcaseCard>

                <ShowcaseCard
                    label="PTT ACTIVE (click to toggle)"
                    code={`<PushToTalkButton active onClick={handler} />`}
                    dark
                >
                    <PushToTalkButton active={pttActive} onClick={() => setPttActive((v) => !v)} />
                </ShowcaseCard>

                <ShowcaseCard label="WAVEFORM METER ACTIVE" code={`<WaveformMeter active />`} dark>
                    <WaveformMeter active />
                </ShowcaseCard>

                <ShowcaseCard
                    label="WAVEFORM METER INACTIVE"
                    code={`<WaveformMeter active={false} />`}
                    dark
                >
                    <WaveformMeter active={false} />
                </ShowcaseCard>

                <ShowcaseCard
                    label="WAVEFORM METER MIRRORED"
                    code={`<WaveformMeter active mirrored />`}
                    dark
                >
                    <WaveformMeter active mirrored />
                </ShowcaseCard>

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

                <ShowcaseCard
                    label="STATUS LABEL (auto-cycling)"
                    code={`<StatusLabel state={state} />`}
                    dark
                >
                    <StatusLabel state={cycledState} />
                </ShowcaseCard>

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

export default PrimitivesInteractiveSection;
