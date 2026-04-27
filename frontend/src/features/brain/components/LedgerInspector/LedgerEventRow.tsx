/**
 * LedgerEventRow — single device event row within the event list.
 */
import type { ReactElement } from 'react';
import { LedgerKindBadge } from '../LedgerKindBadge';
import { relativeTime, payloadPreview } from './utils';
import type { LedgerEventRowProps } from './LedgerEventRow.types';

export function LedgerEventRow({ event }: LedgerEventRowProps): ReactElement {
    return (
        <div data-testid="ledger-event-row" className="flex flex-col gap-0.5 py-1 px-1 hover:bg-slate-800/20 rounded-sm">
            <div className="flex items-center gap-1.5 flex-wrap">
                <LedgerKindBadge kind={event.kind} />
                <span className="text-[8px] text-slate-500 font-mono">{event.source}</span>
                <span className="text-[8px] text-slate-600 ml-auto shrink-0">
                    {relativeTime(event.ts)}
                </span>
            </div>
            <p className="text-[9px] text-slate-500 font-mono truncate pl-0.5">
                {payloadPreview(event.payload)}
            </p>
        </div>
    );
}

export default LedgerEventRow;
