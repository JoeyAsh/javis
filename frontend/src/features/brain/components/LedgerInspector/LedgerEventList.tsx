/**
 * LedgerEventList — scrollable list of device events grouped by correlation_id.
 */
import type { ReactElement } from 'react';
import type { LedgerEventListProps } from './LedgerInspector.types';
import { LedgerEventGroup } from './LedgerEventGroup';
import { groupEventsByCorrelation } from './utils';

export function LedgerEventList({ events }: LedgerEventListProps): ReactElement {
    if (events.length === 0) {
        return (
            <div className="px-3 py-4 text-[10px] text-slate-500 italic text-center">
                No events yet — JARVIS hasn&apos;t logged anything matching the current filter.
            </div>
        );
    }

    const groups = groupEventsByCorrelation(events);

    return (
        <div className="flex flex-col gap-0 px-2 py-1">
            {groups.map(({ key, correlationId, events: groupEvents }) => (
                <LedgerEventGroup
                    key={key}
                    correlationId={correlationId}
                    events={groupEvents}
                />
            ))}
        </div>
    );
}

export default LedgerEventList;
