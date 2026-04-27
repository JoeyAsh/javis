import type { ReactElement } from 'react';
import type { ActivitySourceListProps } from './ActivityPanel.types';
import { statusBadgeClasses } from './utils';

export function ActivitySourceList({ sources }: ActivitySourceListProps): ReactElement {
    const entries = Object.entries(sources);

    if (entries.length === 0) {
        return (
            <div className="px-3 py-2 text-[10px] text-slate-500 italic">No active sources.</div>
        );
    }

    return (
        <div className="px-2 py-1 border-b border-slate-700/40">
            <div className="text-[9px] text-slate-500 uppercase tracking-widest px-1 mb-1">
                Sources
            </div>
            {entries.map(([source, entry]) => (
                <div key={source} className="flex items-center gap-2 py-0.5 px-1">
                    <span
                        className={`text-[8px] px-1.5 py-0.5 rounded-sm font-mono shrink-0 ${statusBadgeClasses(entry.status)}`}
                    >
                        {entry.status}
                    </span>
                    <span className="text-[10px] text-slate-300 font-mono truncate min-w-0">
                        {source}
                    </span>
                    {entry.message.length > 0 && (
                        <span className="text-[9px] text-slate-500 truncate min-w-0">
                            — {entry.message}
                        </span>
                    )}
                </div>
            ))}
        </div>
    );
}

export default ActivitySourceList;
