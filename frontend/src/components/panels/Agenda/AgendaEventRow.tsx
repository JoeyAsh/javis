/**
 * AgendaEventRow — single calendar event list item.
 * Matches prototype `.ev` pattern exactly.
 */
import type { ReactElement } from 'react';
import { useSfx } from '../../../lib/audio/SfxContext';
import type { AgendaEvent } from '../../../types';
import './AgendaPanel.css';

interface EventPill {
    label: string;
    variant: 'now' | 'soon' | 'default';
}

function derivePill(event: AgendaEvent): EventPill | null {
    const minsUntil = Math.round((new Date(event.start).getTime() - Date.now()) / 60_000);
    if (minsUntil <= 0 && Date.now() < new Date(event.end).getTime()) {
        return { label: 'NOW', variant: 'now' };
    }
    if (minsUntil > 0 && minsUntil <= 30) {
        return { label: 'SOON', variant: 'soon' };
    }
    return null;
}

function formatTime(iso: string): string {
    const d = new Date(iso);
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

export interface AgendaEventRowProps {
    event: AgendaEvent;
    onClick?: (event: AgendaEvent) => void;
}

export function AgendaEventRow({ event, onClick }: AgendaEventRowProps): ReactElement {
    const { playOneShot } = useSfx();
    const pill = derivePill(event);
    const sub = event.location ?? event.calendar;

    const pillClass = [
        'agenda-event-row__pill',
        pill?.variant === 'now' ? 'agenda-event-row__pill--now' : '',
        pill?.variant === 'soon' ? 'agenda-event-row__pill--soon' : '',
    ]
        .filter(Boolean)
        .join(' ');

    const handleClick = (): void => {
        playOneShot('click');
        onClick?.(event);
    };

    return (
        <div
            className="agenda-event-row"
            onClick={handleClick}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') handleClick();
            }}
        >
            <span className="agenda-event-row__time">{formatTime(event.start)}</span>
            <div className="agenda-event-row__body">
                <div className="agenda-event-row__title">{event.title}</div>
                {sub && <div className="agenda-event-row__sub">{sub}</div>}
            </div>
            {pill && <span className={pillClass}>{pill.label}</span>}
        </div>
    );
}

export default AgendaEventRow;
