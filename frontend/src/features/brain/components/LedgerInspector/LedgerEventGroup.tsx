/**
 * LedgerEventGroup — renders a group of events sharing a correlation_id,
 * or a flat single event when correlation_id is null.
 */
import type { ReactElement } from 'react';
import { LedgerEventRow } from './LedgerEventRow';
import type { LedgerEventGroupProps } from './LedgerInspector.types';

export function LedgerEventGroup({ correlationId, events }: LedgerEventGroupProps): ReactElement {
    if (correlationId === null || events.length === 1) {
        const event = events[0];
        if (event === undefined) return <></>;
        return <LedgerEventRow event={event} />;
    }

    return (
        <div className="flex flex-col border-l-2 border-slate-700/40 pl-2 py-0.5 my-0.5">
            <div className="text-[7px] font-mono text-slate-600 pb-0.5 truncate">
                {correlationId}
            </div>
            {events.map((ev) => (
                <LedgerEventRow key={ev.id} event={ev} />
            ))}
        </div>
    );
}

export default LedgerEventGroup;
