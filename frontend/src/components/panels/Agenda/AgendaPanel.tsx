/**
 * AgendaPanel — panel body for calendar events.
 * Returns only body content; the Window wrapper supplies chrome via HudPanel.
 *
 * Prototype reference: AgendaPanel() in JARVIS HUD Hypermodern.html
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import type { ReactElement } from 'react';
import type { AgendaEvent, CalendarStatePayload, PanelMode } from '../../../types';
import { subscribeCalendarStateStream } from '../../../hooks/useWebSocket';
import { usePanelAvailable } from '../../hud/PanelAvailability';
import { AgendaEventRow } from './AgendaEventRow';
import './AgendaPanel.css';

const AVAILABILITY_TIMEOUT_MS = 10_000;

function minutesUntil(iso: string): number {
    return Math.max(0, Math.round((new Date(iso).getTime() - Date.now()) / 60_000));
}

// ---- Compact mode ----

function AgendaCompact({ events }: { events: AgendaEvent[] }): ReactElement {
    const next = events[0];
    if (!next) {
        return (
            <div className="agenda-compact">
                <span className="agenda-empty">Keine Termine heute</span>
            </div>
        );
    }
    const mins = minutesUntil(next.start);
    const sub = next.location ?? next.calendar;
    return (
        <div className="agenda-compact">
            <div className="agenda-compact__header">
                <span className="agenda-compact__dot" aria-hidden />
                <span className="agenda-compact__label">NÄCHSTER</span>
                <span className="agenda-compact__until">in {mins}min</span>
            </div>
            <div className="agenda-compact__title">{next.title}</div>
            {sub && <div className="agenda-compact__meta">{sub}</div>}
        </div>
    );
}

// ---- Expanded mode ----

function AgendaExpanded({ events }: { events: AgendaEvent[] }): ReactElement {
    const upcoming = events.slice(0, 4);
    if (upcoming.length === 0) {
        return (
            <div className="agenda-panel">
                <span className="agenda-empty">Keine Termine in den nächsten 48 Stunden</span>
            </div>
        );
    }
    return (
        <div className="agenda-panel">
            {upcoming.map((evt) => (
                <AgendaEventRow key={evt.id} event={evt} />
            ))}
        </div>
    );
}

// ---- Props + main export ----

export interface AgendaPanelProps {
    events?: AgendaEvent[];
    mode?: PanelMode;
}

/**
 * AgendaPanel body — renders upcoming calendar events.
 * Accepts optional `events` prop for testing; otherwise subscribes to live WS.
 * Returns null if no backend payload arrives within AVAILABILITY_TIMEOUT_MS.
 */
export function AgendaPanel({
    events: eventsProp,
    mode = 'expanded',
}: AgendaPanelProps): ReactElement | null {
    const [liveEvents, setLiveEvents] = useState<AgendaEvent[]>([]);
    const [hasLiveData, setHasLiveData] = useState(false);
    const [backendAvailable, setBackendAvailable] = useState(true);
    const availabilityTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Report availability to HudWindows so it can filter the panel entirely.
    usePanelAvailable('agenda', backendAvailable || hasLiveData);

    useEffect(() => {
        if (eventsProp !== undefined) return;

        availabilityTimerRef.current = setTimeout(() => {
            setBackendAvailable(false);
        }, AVAILABILITY_TIMEOUT_MS);

        const unsub = subscribeCalendarStateStream((payload: CalendarStatePayload) => {
            if (availabilityTimerRef.current) clearTimeout(availabilityTimerRef.current);
            setLiveEvents(payload.events);
            setHasLiveData(true);
            setBackendAvailable(true);
        });
        return () => {
            if (availabilityTimerRef.current) clearTimeout(availabilityTimerRef.current);
            unsub();
        };
    }, [eventsProp]);

    const list = useMemo<AgendaEvent[]>(() => {
        if (eventsProp !== undefined) return eventsProp;
        return liveEvents;
    }, [eventsProp, liveEvents]);

    // Backend not available — hide the panel.
    if (eventsProp === undefined && !backendAvailable && !hasLiveData) return null;

    // Still waiting for first payload.
    if (eventsProp === undefined && !hasLiveData) {
        return (
            <div className="agenda-panel">
                <span className="agenda-loading">Kalender wird geladen…</span>
            </div>
        );
    }

    return mode === 'compact' ? <AgendaCompact events={list} /> : <AgendaExpanded events={list} />;
}

export default AgendaPanel;
