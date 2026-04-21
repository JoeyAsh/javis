import { useEffect, type ReactElement } from 'react';
import { useClickSfx, useHoverSfx } from '../audio/hooks';
import './Tweaks.css';

export interface TweaksState {
    hue: number;
    glow: number;
    scan: boolean;
    grid: boolean;
    rings: boolean;
    particles: boolean;
    idleDim: boolean;
}

export const TWEAKS_DEFAULTS: TweaksState = {
    hue: 215,
    glow: 74,
    scan: true,
    grid: true,
    rings: true,
    particles: true,
    idleDim: true,
};

/** Writes accent CSS variables to :root, reacting to hue + glow changes. */
export function useTweakApply(tweaks: TweaksState): void {
    useEffect(() => {
        const r = document.documentElement;
        r.style.setProperty('--tweak-hue', String(tweaks.hue));
        const l = 0.72;
        const c = 0.14;
        r.style.setProperty('--accent', `oklch(${l} ${c} ${tweaks.hue})`);
        r.style.setProperty('--accent-bright', `oklch(${l + 0.1} ${c + 0.02} ${tweaks.hue})`);
        r.style.setProperty('--accent-speak', `oklch(${l + 0.05} ${c + 0.01} ${tweaks.hue})`);
        r.style.setProperty('--accent-dim', `oklch(${l - 0.2} ${c - 0.04} ${tweaks.hue})`);
        r.style.setProperty(
            '--glow',
            `0 0 ${6 + tweaks.glow * 0.1}px oklch(${l} ${c} ${tweaks.hue} / ${0.4 + tweaks.glow * 0.005})`,
        );
        r.style.setProperty(
            '--glow-strong',
            `0 0 ${12 + tweaks.glow * 0.2}px oklch(${l} ${c} ${tweaks.hue} / ${0.5 + tweaks.glow * 0.005}), 0 0 ${28 + tweaks.glow * 0.3}px oklch(${l} ${c} ${tweaks.hue} / ${0.25 + tweaks.glow * 0.003})`,
        );
    }, [tweaks]);
}

const HUE_SWATCHES = [215, 28, 150, 280, 0];

interface ToggleRowProps {
    label: string;
    value: boolean;
    onToggle: () => void;
}

function ToggleRow({ label, value, onToggle }: ToggleRowProps): ReactElement {
    const hoverSfx = useHoverSfx('button');
    const clickSfx = useClickSfx(onToggle);
    return (
        <div className="lib-tweaks__row">
            <span>{label}</span>
            <button
                type="button"
                className={['lib-tweaks__toggle', value && 'on'].filter(Boolean).join(' ')}
                onClick={clickSfx}
                onMouseEnter={hoverSfx}
                aria-pressed={value}
                aria-label={label}
                data-sfx-hover="button"
            />
        </div>
    );
}

export interface TweaksProps {
    open: boolean;
    tweaks: TweaksState;
    onChange: (next: TweaksState) => void;
    className?: string;
}

export function Tweaks({ open, tweaks, onChange, className }: TweaksProps): ReactElement {
    function upd<K extends keyof TweaksState>(key: K, value: TweaksState[K]): void {
        onChange({ ...tweaks, [key]: value });
    }

    const classes = ['lib-tweaks', open && 'open', className].filter(Boolean).join(' ');

    return (
        <div className={classes}>
            <h3 className="lib-tweaks__heading">◈ TWEAKS</h3>

            {/* Accent Hue */}
            <div className="lib-tweaks__field">
                <label htmlFor="lib-tweaks-hue">
                    Accent Hue <span className="lib-tweaks__val">{tweaks.hue}°</span>
                </label>
                <input
                    id="lib-tweaks-hue"
                    type="range"
                    min={0}
                    max={360}
                    value={tweaks.hue}
                    onChange={(e) => upd('hue', Number(e.target.value))}
                />
                <div className="lib-tweaks__swatches">
                    {HUE_SWATCHES.map((h) => (
                        <SwatchButton
                            key={h}
                            hue={h}
                            active={tweaks.hue === h}
                            onSelect={() => upd('hue', h)}
                        />
                    ))}
                </div>
            </div>

            {/* Glow Intensity */}
            <div className="lib-tweaks__field">
                <label htmlFor="lib-tweaks-glow">
                    Glow intensity <span className="lib-tweaks__val">{tweaks.glow}</span>
                </label>
                <input
                    id="lib-tweaks-glow"
                    type="range"
                    min={0}
                    max={100}
                    value={tweaks.glow}
                    onChange={(e) => upd('glow', Number(e.target.value))}
                />
            </div>

            <ToggleRow
                label="Scanlines"
                value={tweaks.scan}
                onToggle={() => upd('scan', !tweaks.scan)}
            />
            <ToggleRow
                label="Grid"
                value={tweaks.grid}
                onToggle={() => upd('grid', !tweaks.grid)}
            />
            <ToggleRow
                label="Rings"
                value={tweaks.rings}
                onToggle={() => upd('rings', !tweaks.rings)}
            />
            <ToggleRow
                label="Particles"
                value={tweaks.particles}
                onToggle={() => upd('particles', !tweaks.particles)}
            />
            <ToggleRow
                label="Idle dim"
                value={tweaks.idleDim}
                onToggle={() => upd('idleDim', !tweaks.idleDim)}
            />
        </div>
    );
}

interface SwatchButtonProps {
    hue: number;
    active: boolean;
    onSelect: () => void;
}

function SwatchButton({ hue, active, onSelect }: SwatchButtonProps): ReactElement {
    const hoverSfx = useHoverSfx('button');
    const clickSfx = useClickSfx(onSelect);
    return (
        <button
            type="button"
            className={['lib-tweaks__swatch', active && 'active'].filter(Boolean).join(' ')}
            style={{ background: `oklch(0.72 0.14 ${hue})` }}
            onClick={clickSfx}
            onMouseEnter={hoverSfx}
            aria-label={`Hue ${hue}`}
            data-sfx-hover="button"
        />
    );
}

export default Tweaks;
