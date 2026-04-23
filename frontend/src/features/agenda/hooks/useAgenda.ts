import { useAppSelector } from '@app';
import { useStreamAgendaQuery } from '../agendaApi';
import { selectAgendaEvents, selectAgendaHasLiveData } from '../agendaSelectors';
import type { UseAgendaReturn } from './useAgenda.types';

export function useAgenda(): UseAgendaReturn {
    useStreamAgendaQuery();

    const events = useAppSelector(selectAgendaEvents);
    const hasLiveData = useAppSelector(selectAgendaHasLiveData);

    return { events, hasLiveData };
}
