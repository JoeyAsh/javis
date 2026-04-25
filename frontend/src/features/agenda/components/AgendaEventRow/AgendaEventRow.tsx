import type { ReactElement } from 'react';
import { useSfx } from '@core/audio';
import { formatTime } from '@common/utils/time';
import type { AgendaEventRowProps } from './AgendaEventRow.types';
import { derivePill } from './utils';
import styles from './AgendaEventRow.module.css';

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
