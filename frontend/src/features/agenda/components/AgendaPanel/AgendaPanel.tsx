/**
 * AgendaPanel — panel body for calendar events.
 * Data comes from the Redux agenda slice via useAgenda hook (or eventsProp override).
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import type { ReactElement } from 'react';
import { usePanelAvailable } from '@app/providers/PanelAvailabilityProvider';
import { useAgenda } from '../../hooks/useAgenda';
import { AgendaEventRow } from '../AgendaEventRow';
import type { AgendaEvent } from '../../types';
import type { AgendaPanelProps } from './AgendaPanel.types';
import styles from './AgendaPanel.module.css';

const AVAILABILITY_TIMEOUT_MS = 10_000;

function minutesUntil(iso: string): number {
    return Math.max(0, Math.round((new Date(iso).getTime() - Date.now()) / 60_000));
}

// ---- Compact mode ----

function AgendaCompact({ events }: { events: AgendaEvent[] }): ReactElement {
    const next = events[0];
    if (!next) {
        return (
            <div className={styles.compact}>
                <span className={styles.empty}>Keine Termine heute</span>
            </div>
        );
    }
    const mins = minutesUntil(next.start);
    const sub = next.location ?? next.calendar;
    return (
        <div className={styles.compact}>
            <div className={styles.header}>
                <span className={styles.dot} aria-hidden />
                <span className={styles.label}>NÄCHSTER</span>
                <span className={styles.until}>in {mins}min</span>
            </div>
            <div className={styles.title}>{next.title}</div>
            {sub && <div className={styles.meta}>{sub}</div>}
        </div>
    );
}

// ---- Expanded mode ----

function AgendaExpanded({ events }: { events: AgendaEvent[] }): ReactElement {
    const upcoming = events.slice(0, 4);
    if (upcoming.length === 0) {
        return (
            <div className={styles.panel}>
                <span className={styles.empty}>Keine Termine in den nächsten 48 Stunden</span>
            </div>
        );
    }
    return (
        <div className={styles.panel}>
            {upcoming.map((evt) => (
                <AgendaEventRow key={evt.id} event={evt} />
            ))}
        </div>
    );
}

// ---- Main export ----

/**
 * AgendaPanel body — renders upcoming calendar events.
 * Accepts optional `events` prop for testing; otherwise uses live Redux state.
 * Returns loading state if no backend payload has arrived yet.
 * Shows unavailable-state if no payload arrives within 10 s.
 */
export function AgendaPanel({ events: eventsProp, mode = 'expanded' }: AgendaPanelProps): ReactElement | null {
    const { events: liveEvents, hasLiveData } = useAgenda();
    const [backendAvailable, setBackendAvailable] = useState(true);
    const availabilityTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    usePanelAvailable('agenda', backendAvailable || hasLiveData);

    useEffect(() => {
        if (eventsProp !== undefined) return;

        availabilityTimerRef.current = setTimeout(() => {
            setBackendAvailable(false);
        }, AVAILABILITY_TIMEOUT_MS);

        return () => {
            if (availabilityTimerRef.current) clearTimeout(availabilityTimerRef.current);
        };
    }, [eventsProp]);

    // Cancel availability timer once live data arrives.
    useEffect(() => {
        if (hasLiveData && availabilityTimerRef.current) {
            clearTimeout(availabilityTimerRef.current);
            availabilityTimerRef.current = null;
            setBackendAvailable(true);
        }
    }, [hasLiveData]);

    const list = useMemo<AgendaEvent[]>(() => {
        if (eventsProp !== undefined) return eventsProp;
        return liveEvents;
    }, [eventsProp, liveEvents]);

    // Backend not available — hide panel entirely.
    if (eventsProp === undefined && !backendAvailable && !hasLiveData) return null;

    // Still waiting for first payload.
    if (eventsProp === undefined && !hasLiveData) {
        return (
            <div className={styles.panel}>
                <span className={styles.loading}>Kalender wird geladen…</span>
            </div>
        );
    }

    return mode === 'compact' ? <AgendaCompact events={list} /> : <AgendaExpanded events={list} />;
}

export default AgendaPanel;
