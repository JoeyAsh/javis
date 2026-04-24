import { type ReactElement } from 'react';
import type { AppOrbState } from '@common/types';
import type { StatusLabelProps } from './StatusLabel.types';

const STATE_LABELS: Record<AppOrbState, string> = {
    idle: 'READY',
    listening: 'listening...',
    thinking: 'thinking...',
    speaking: 'speaking...',
    follow_up: 'listening...',
    working: 'working...',
};

export function StatusLabel({
    state,
    brand = 'J A R V I S',
    className,
}: StatusLabelProps): ReactElement {
    const isActive = state !== 'idle';
    const stateClass = ['lib-status-label__state', isActive && 'active'].filter(Boolean).join(' ');

    return (
        <div className={['lib-status-label', className].filter(Boolean).join(' ')}>
            <span className={stateClass}>{STATE_LABELS[state]}</span>
            <span className="lib-status-label__brand">{brand}</span>
        </div>
    );
}

export default StatusLabel;
