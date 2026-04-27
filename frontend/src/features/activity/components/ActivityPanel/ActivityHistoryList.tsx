import type { ReactElement } from 'react';
import type { ActivityHistoryListProps } from './ActivityPanel.types';
import { severityBadgeClasses, relativeTime } from './utils';

export function ActivityHistoryList({ history }: ActivityHistoryListProps): ReactElement {
    if (history.length === 0) {
        return (
            <div className="px-3 py-2 text-[10px] text-slate-500 italic">
                No recent narrations.
            </div>
        );
    }

    return (
        <div className="flex flex-col gap-0.5 px-2 py-1 overflow-y-auto min-h-0">
            {history.map((item) => (
                <div
                    key={item.id}
                    className="flex flex-col gap-0.5 px-1 py-1 hover:bg-slate-800/30 rounded-sm"
                >
                    <div className="flex items-center gap-2">
                        <span
                            className={`text-[8px] px-1.5 py-0.5 rounded-sm font-mono shrink-0 ${severityBadgeClasses(item.severity)}`}
                        >
                            {item.severity}
                        </span>
                        {item.source !== null && (
                            <span className="text-[9px] text-slate-500 font-mono truncate min-w-0">
                                {item.source}
                            </span>
                        )}
                        <span className="text-[9px] text-slate-600 ml-auto shrink-0">
                            {relativeTime(item.created_at)}
                        </span>
                    </div>
                    <p className="text-[10px] text-slate-300 leading-tight line-clamp-2 px-0.5">
                        {item.text}
                    </p>
                </div>
            ))}
        </div>
    );
}

export default ActivityHistoryList;
