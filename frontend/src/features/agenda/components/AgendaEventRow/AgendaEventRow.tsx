import type { ReactElement } from 'react';
import { useSfx } from '@core/audio';
import type { AgendaEvent } from '../../types';
import type { AgendaEventRowProps } from './AgendaEventRow.types';
import styles from './AgendaEventRow.module.css';

type EventPill = {
    label: string;
    variant: 'now' | 'soon';
};

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

export function AgendaEventRow({ event, onClick }: AgendaEventRowProps): ReactElement {
    const { playOneShot } = useSfx();
    const pill = derivePill(event);
    const sub = event.location ?? event.calendar;

    const pillClass = [
        styles.pill,
        pill?.variant === 'now' ? styles.pillNow : '',
        pill?.variant === 'soon' ? styles.pillSoon : '',
    ]
        .filter(Boolean)
        .join(' ');

    const handleClick = (): void => {
        playOneShot('click');
        onClick?.(event);
    };

    return (
        <div
            className={styles.row}
            onClick={handleClick}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') handleClick();
            }}
        >
            <span className={styles.time}>{formatTime(event.start)}</span>
            <div className={styles.body}>
                <div className={styles.title}>{event.title}</div>
                {sub && <div className={styles.sub}>{sub}</div>}
            </div>
            {pill && <span className={pillClass}>{pill.label}</span>}
        </div>
    );
}

export default AgendaEventRow;
