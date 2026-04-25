import type { AgendaEvent } from '../types';

export interface UseAgendaReturn {
    events: AgendaEvent[];
    hasLiveData: boolean;
}
