import { useEffect, useState } from 'react';
import type { ReactElement } from 'react';
import styles from '../TopBar.module.css';
import type { TimeWidgetProps } from './TimeWidget.types';

const DEFAULT_LOCALE = 'de-DE';
const DEFAULT_TZ = 'Europe/Berlin';
const TICK_MS = 1_000;

export function TimeWidget({
    locale = DEFAULT_LOCALE,
    timeZone = DEFAULT_TZ,
}: TimeWidgetProps): ReactElement {
    const [now, setNow] = useState<Date>(() => new Date());

    useEffect(() => {
        const id = window.setInterval(() => setNow(new Date()), TICK_MS);
        return () => window.clearInterval(id);
    }, []);

    const timeFmt = new Intl.DateTimeFormat(locale, {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
        timeZone,
    });

    const dateFmt = new Intl.DateTimeFormat(locale, {
        weekday: 'long',
        day: 'numeric',
        month: 'long',
        year: 'numeric',
        timeZone,
    });

    return (
        <>
            <span className={styles.clock} aria-label="Current time">
                {timeFmt.format(now)}
            </span>
            <span className={styles.sep} aria-hidden="true">·</span>
            <span className={styles.date} aria-label="Current date">
                {dateFmt.format(now)}
            </span>
        </>
    );
}

export default TimeWidget;
