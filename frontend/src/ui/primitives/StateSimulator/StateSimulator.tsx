import { type ReactElement } from 'react';
import { useClickSfx, useHoverSfx } from '@core/audio';
import type { StateSimulatorProps, SimOption, SimButtonProps } from './StateSimulator.types';
import './StateSimulator.css';

const SIM_OPTIONS: SimOption[] = [
    { key: 'idle', label: 'IDLE' },
    { key: 'listening', label: 'LISTENING' },
    { key: 'thinking', label: 'THINKING' },
    { key: 'speaking', label: 'SPEAKING' },
    { key: 'working', label: 'WORKING' },
];

function SimButton({ option, active, onChange }: SimButtonProps): ReactElement {
    const hoverSfx = useHoverSfx('button');
    const clickSfx = useClickSfx(() => onChange(option.key));
    const btnClass = [
        'lib-sim__btn',
        active && 'active',
        active && option.key === 'working' && 'working',
    ]
        .filter(Boolean)
        .join(' ');
    return (
        <button
            key={option.key}
            type="button"
            className={btnClass}
            onClick={clickSfx}
            onMouseEnter={hoverSfx}
            data-sfx-hover="button"
        >
            <span className="lib-sim__dot" aria-hidden="true" />
            {option.label}
        </button>
    );
}

export function StateSimulator({
    state,
    onChange,
    label = '◈ ORB STATE',
    position = 'fixed-top',
    className,
}: StateSimulatorProps): ReactElement {
    const classes = ['lib-sim', position, className].filter(Boolean).join(' ');

    return (
        <div className={classes}>
            <span className="lib-sim__label">{label}</span>
            {SIM_OPTIONS.map((opt) => (
                <SimButton key={opt.key} option={opt} active={state === opt.key} onChange={onChange} />
            ))}
        </div>
    );
}

export default StateSimulator;
