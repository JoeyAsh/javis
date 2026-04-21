import { type ReactElement } from 'react';
import type { OrbState } from './Orb/Orb';
import './StateSimulator.css';

interface SimOption {
    key: OrbState;
    label: string;
}

const SIM_OPTIONS: SimOption[] = [
    { key: 'idle', label: 'IDLE' },
    { key: 'listening', label: 'LISTENING' },
    { key: 'thinking', label: 'THINKING' },
    { key: 'speaking', label: 'SPEAKING' },
    { key: 'working', label: 'WORKING' },
];

export interface StateSimulatorProps {
    state: OrbState;
    onChange: (state: OrbState) => void;
    label?: string;
    position?: 'fixed-top' | 'inline';
    className?: string;
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
            {SIM_OPTIONS.map((opt) => {
                const isActive = state === opt.key;
                const btnClass = [
                    'lib-sim__btn',
                    isActive && 'active',
                    isActive && opt.key === 'working' && 'working',
                ]
                    .filter(Boolean)
                    .join(' ');
                return (
                    <button
                        key={opt.key}
                        type="button"
                        className={btnClass}
                        onClick={() => onChange(opt.key)}
                    >
                        <span className="lib-sim__dot" aria-hidden="true" />
                        {opt.label}
                    </button>
                );
            })}
        </div>
    );
}

export default StateSimulator;
