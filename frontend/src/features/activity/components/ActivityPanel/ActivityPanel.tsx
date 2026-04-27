/**
 * ActivityPanel — real-time narration activity feed.
 * Shows quiet-mode indicator, per-source status, and narration history.
 * Always visible in the HUD; data flows from the activity Redux slice
 * populated by `narration_state` and `activity_panel` WS messages.
 */
import type { ReactElement } from 'react';
import { useActivity } from '../../hooks/useActivity';
import { ActivityQuietBar } from './ActivityQuietBar';
import { ActivitySourceList } from './ActivitySourceList';
import { ActivityHistoryList } from './ActivityHistoryList';
import type { ActivityPanelProps } from './ActivityPanel.types';

export function ActivityPanel({ mode = 'expanded' }: ActivityPanelProps): ReactElement {
    const { quietUntil, sources, history, hasLiveData } = useActivity();

    if (!hasLiveData) {
        return (
            <div className="flex flex-col h-full">
                <div className="px-3 py-2 text-[10px] text-slate-500 italic">
                    Waiting for activity data…
                </div>
            </div>
        );
    }

    if (mode === 'compact') {
        return (
            <div className="flex flex-col">
                {quietUntil !== null && <ActivityQuietBar quietUntil={quietUntil} />}
                <ActivityHistoryList history={history.slice(0, 5)} />
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full overflow-hidden">
            {quietUntil !== null && <ActivityQuietBar quietUntil={quietUntil} />}
            <ActivitySourceList sources={sources} />
            <div className="flex-1 min-h-0 overflow-y-auto">
                <div className="text-[9px] text-slate-500 uppercase tracking-widest px-3 pt-2 pb-1">
                    History
                </div>
                <ActivityHistoryList history={history} />
            </div>
        </div>
    );
}

export default ActivityPanel;
