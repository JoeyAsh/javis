import { type ReactElement } from 'react';
import { WaveformMeter } from '../../primitives/WaveformMeter';
import { PushToTalkButton } from '../../primitives/PushToTalkButton';
import { StatusLabel } from '../../primitives/StatusLabel';
import type { StatusDockProps } from './StatusDock.types';
import './StatusDock.css';

export function StatusDock({ state, onPTT, ptt, className }: StatusDockProps): ReactElement {
    const isActive = state !== 'idle';
    const classes = ['lib-dock', className].filter(Boolean).join(' ');

    return (
        <div className={classes}>
            <div className="lib-dock__controls">
                <WaveformMeter active={isActive} />
                {ptt ?? <PushToTalkButton active={isActive} onClick={onPTT} />}
                <WaveformMeter active={isActive} mirrored />
            </div>
            <StatusLabel state={state} />
        </div>
    );
}

export default StatusDock;
