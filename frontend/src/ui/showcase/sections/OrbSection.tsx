import { useState, type ReactElement } from 'react';
import { CssOrb } from '../../orb/CssOrb';
import type { AppOrbState } from '@common/types';
import { Button } from '../../primitives/Button';
import { StateSimulator } from '../../primitives/StateSimulator';
import { Mono } from '../../primitives/Mono';

const ALL_STATES: AppOrbState[] = ['idle', 'listening', 'thinking', 'speaking', 'working'];

export function OrbSection(): ReactElement {
    const [liveState, setLiveState] = useState<AppOrbState>('idle');
    const [rings, setRings] = useState(true);
    const [particles, setParticles] = useState(true);

    const codeStr = `<Orb state="${liveState}" ${rings ? 'rings' : 'rings={false}'} ${particles ? 'particles' : 'particles={false}'} />`;

    return (
        <section id="orb" className="flex flex-col gap-6">
            <div>
                <h2 className="text-[12px] text-text font-mono mb-1">ORB</h2>
                <p className="text-[10px] text-text-secondary font-mono">
                    5 states · Pulse rings (listening) · Particles · RAF-driven particles ·
                    Motion-reduce aware. Values ported byte-for-byte from the handoff prototype.
                </p>
            </div>

            {/* Side-by-side state comparison — 5 × 300×300 frames */}
            <div className="flex flex-col gap-2">
                <span className="text-[9px] uppercase tracking-[2px] font-mono text-text-secondary">
                    All 5 States Side-by-Side
                </span>
                <div className="flex gap-3 flex-wrap">
                    {ALL_STATES.map((s) => (
                        <div key={s} className="flex flex-col items-center gap-2">
                            <div
                                className="border border-border overflow-hidden"
                                style={{
                                    position: 'relative',
                                    width: 300,
                                    height: 300,
                                    background: '#050508',
                                }}
                            >
                                <CssOrb state={s} particles />
                            </div>
                            <span className="text-[9px] uppercase tracking-[2px] font-mono text-text-secondary">
                                {s}
                            </span>
                        </div>
                    ))}
                </div>
            </div>

            {/* Live full-size demo */}
            <div className="flex flex-col gap-3">
                <span className="text-[9px] uppercase tracking-[2px] font-mono text-text-secondary">
                    Full-Size Live Demo (920 × 920 wrapper)
                </span>

                {/* StateSimulator inline */}
                <StateSimulator state={liveState} onChange={setLiveState} position="inline" />

                {/* Rings + Particles toggles */}
                <div className="flex items-center gap-3">
                    <Button
                        variant={rings ? 'secondary' : 'ghost'}
                        size="sm"
                        onClick={() => setRings((r) => !r)}
                    >
                        RINGS {rings ? 'ON' : 'OFF'}
                    </Button>
                    <Button
                        variant={particles ? 'secondary' : 'ghost'}
                        size="sm"
                        onClick={() => setParticles((p) => !p)}
                    >
                        particles {particles ? 'ON' : 'OFF'}
                    </Button>
                </div>

                {/* Code hint */}
                <Mono size="xs" className="text-accent-bright">
                    {codeStr}
                </Mono>

                {/* Orb stage — position:relative so anchor-only orb-wrap centers within */}
                <div
                    className="overflow-hidden border border-border"
                    style={{
                        position: 'relative',
                        background: 'rgba(5,5,8,0.95)',
                        height: '960px',
                        backgroundImage:
                            'linear-gradient(rgba(76,168,232,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(76,168,232,0.04) 1px, transparent 1px)',
                        backgroundSize: '44px 44px',
                    }}
                >
                    <CssOrb state={liveState} rings={rings} particles={particles} />
                </div>
            </div>
        </section>
    );
}

export default OrbSection;
