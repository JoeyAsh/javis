import type { AgendaEvent } from '../../types';

export interface AgendaEventRowProps {
    event: AgendaEvent;
    onClick?: (event: AgendaEvent) => void;
}
