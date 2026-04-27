/**
 * LedgerInspector — device event ledger panel.
 * Shows voice composer status, 24h kind counts, kind + time filters,
 * and a live-updating scrollable list of the last 50 device events.
 */
import type { ReactElement } from 'react';
import { useBrain } from '../../hooks/useBrain';
import { LedgerHeader } from './LedgerHeader';
import { LedgerFilterRow } from './LedgerFilterRow';
import { LedgerEventList } from './LedgerEventList';
import type { LedgerInspectorProps } from './LedgerInspector.types';

export function LedgerInspector({ mode = 'expanded' }: LedgerInspectorProps): ReactElement {
    const {
        voiceComposerStatus,
        filteredEvents,
        counts24h,
        kindFilter,
        sinceFilter,
        setKinds,
        setSince,
    } = useBrain();

    if (mode === 'compact') {
        return (
            <div className="flex flex-col h-full overflow-hidden">
                <LedgerEventList events={filteredEvents.slice(0, 5)} />
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full overflow-hidden">
            <LedgerHeader
                voiceComposerStatus={voiceComposerStatus}
                counts24h={counts24h}
            />
            <LedgerFilterRow
                kindFilter={kindFilter}
                sinceMs={sinceFilter}
                onKindsChange={setKinds}
                onSinceChange={setSince}
            />
            <div className="flex-1 min-h-0 overflow-y-auto">
                <LedgerEventList events={filteredEvents} />
            </div>
        </div>
    );
}

export default LedgerInspector;
