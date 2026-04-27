import type { ReactElement } from 'react';
import type { ActivityQuietBarProps } from './ActivityPanel.types';
import { formatQuietUntilTime } from './utils';

export function ActivityQuietBar({ quietUntil }: ActivityQuietBarProps): ReactElement {
    const until = formatQuietUntilTime(quietUntil);
    return (
        <div className="flex items-center gap-2 px-3 py-1.5 bg-amber-900/50 border-b border-amber-700/50">
            <span className="text-amber-400 text-[9px] font-bold tracking-widest">QUIET MODE</span>
            <span className="text-amber-300/70 text-[9px]">— until {until}</span>
        </div>
    );
}

export default ActivityQuietBar;
