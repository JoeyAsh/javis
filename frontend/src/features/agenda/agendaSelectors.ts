import type { RootState } from '@app';
import type { AgendaEvent, CalendarOpPreviewPayload } from './types';

export function selectAgendaEvents(state: RootState): AgendaEvent[] {
    return state.agenda.events;
}

export function selectAgendaHasLiveData(state: RootState): boolean {
    return state.agenda.hasLiveData;
}

export function selectAgendaPendingOp(state: RootState): CalendarOpPreviewPayload | null {
    return state.agenda.pendingOp;
}
