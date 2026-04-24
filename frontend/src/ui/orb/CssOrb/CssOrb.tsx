import { useEffect, useRef, type ReactElement } from 'react';
import { cx } from '@common/utils/cx';
import type { CssOrbProps, ParticleConfig } from './CssOrb.types';

const TICK_ANGLES = Array.from({ length: 36 }, (_, i) => i * 10);

const PARTICLE_CONFIGS: ParticleConfig[] = [
    { radius: 180, dir: 1, period: 10, phase: 0.0, size: 3, colorVar: '--accent-bright' },
    { radius: 210, dir: -1, period: 14, phase: 1.05, size: 2, colorVar: '--accent' },
    { radius: 240, dir: 1, period: 16, phase: 2.1, size: 2, colorVar: '--accent-bright' },
    { radius: 265, dir: -1, period: 20, phase: 3.15, size: 3, colorVar: '--accent' },
    { radius: 295, dir: 1, period: 24, phase: 4.2, size: 2, colorVar: '--accent-speak' },
    { radius: 330, dir: -1, period: 28, phase: 5.25, size: 3, colorVar: '--accent-bright' },
];

export function CssOrb({ state, rings = true, particles = true, className }: CssOrbProps): ReactElement {
    const particleRefs = useRef<(HTMLDivElement | null)[]>([]);
    const rafRef = useRef<number>(0);

    useEffect(() => {
        if (!particles) {
            if (rafRef.current) {
                cancelAnimationFrame(rafRef.current);
                rafRef.current = 0;
            }
            return;
        }

        const loop = (timestamp: number): void => {
            const t = timestamp / 1000;
            PARTICLE_CONFIGS.forEach((cfg, i) => {
                const el = particleRefs.current[i];
                if (!el) return;
                const angle = ((t * 2 * Math.PI) / cfg.period) * cfg.dir + cfg.phase;
                const x = Math.cos(angle) * cfg.radius;
                const y = Math.sin(angle) * cfg.radius;
                el.style.transform = `translate(${x.toFixed(2)}px, ${y.toFixed(2)}px)`;
            });
            rafRef.current = requestAnimationFrame(loop);
        };

        rafRef.current = requestAnimationFrame(loop);

        return () => {
            if (rafRef.current) {
                cancelAnimationFrame(rafRef.current);
                rafRef.current = 0;
            }
        };
    }, [particles]);

    const isWorking = state === 'working';

    return (
        <div
            className={cx('orb-wrap', isWorking && 'is-working', className)}
            aria-label={`Orb: ${state}`}
        >
            {rings && (
                <>
                    <div className="orb-ring r5" />
                    <div className="orb-ring r4" />
                    <div className="orb-ring r3" />
                    <div className="orb-ring r2" />
                    <div className="orb-ring-ticks" aria-hidden>
                        {TICK_ANGLES.map((deg) => (
                            <i
                                key={deg}
                                style={{ transform: `translateX(-50%) rotate(${deg}deg)` }}
                            />
                        ))}
                    </div>
                    <div className="orb-ring r1" />
                </>
            )}

            <div className={`orb state-${state}`} aria-hidden />

            <div className="pulse d1" aria-hidden />
            <div className="pulse d2" aria-hidden />
            <div className="pulse d3" aria-hidden />

            {particles &&
                PARTICLE_CONFIGS.map((cfg, i) => (
                    <div
                        key={i}
                        className="particle"
                        aria-hidden
                        style={{
                            width: cfg.size,
                            height: cfg.size,
                            background: `var(${cfg.colorVar})`,
                            boxShadow: `0 0 ${cfg.size * 3}px var(${cfg.colorVar})`,
                        }}
                        ref={(el) => {
                            particleRefs.current[i] = el;
                        }}
                    />
                ))}
        </div>
    );
}

export { CssOrb as default };
