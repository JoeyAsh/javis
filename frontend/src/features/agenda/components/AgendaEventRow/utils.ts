import type { AgendaEvent } from '../../types';
import type { EventPill } from './AgendaEventRow.types';

export function derivePill(event: AgendaEvent): EventPill | null {
    const minsUntil = Math.round((new Date(event.start).getTime() - Date.now()) / 60_000);
    if (minsUntil <= 0 && Date.now() < new Date(event.end).getTime()) {
        return { label: 'NOW', variant: 'now' };
    }
    if (minsUntil > 0 && minsUntil <= 30) {
        return { label: 'SOON', variant: 'soon' };
    }
    return null;
}
