/**
 * AgendaView — calendar events panel content.
 *
 * Replaces legacy components/panels/Agenda/AgendaPanel.tsx.
 * Uses lib Label, Pill, Mono.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import type { ReactElement } from 'react';
import { Label, Mono, Pill } from '../lib';
import { useSfx } from '../lib/audio/SfxContext';
import type { AgendaEvent, CalendarStatePayload, PanelMode } from '../types';
import { subscribeCalendarStateStream } from '../hooks/useWebSocket';
import { usePanelAvailable } from '../contexts/PanelAvailability';
import './AgendaView.css';

const AVAILABILITY_TIMEOUT_MS = 10_000;

export interface AgendaViewProps {
    events?: AgendaEvent[];
    mode?: PanelMode;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function minutesUntil(iso: string): number {
    return Math.max(0, Math.round((new Date(iso).getTime() - Date.now()) / 60_000));
}

function formatTime(iso: string): string {
    const d = new Date(iso);
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

type PillInfo = { label: string; variant: 'now' | 'soon' };

function derivePill(event: AgendaEvent): PillInfo | null {
    const minsUntil = Math.round((new Date(event.start).getTime() - Date.now()) / 60_000);
    if (minsUntil <= 0 && Date.now() < new Date(event.end).getTime()) {
        return { label: 'NOW', variant: 'now' };
    }
    if (minsUntil > 0 && minsUntil <= 30) {
        return { label: 'SOON', variant: 'soon' };
    }
    return null;
}

// ── Event row ────────────────────────────────────────────────────────────────

function AgendaEventRow({ event }: { event: AgendaEvent }): ReactElement {
    const { playOneShot } = useSfx();
    const pill = derivePill(event);
    const sub = event.location ?? event.calendar;

    return (
        <div
            className="av-row"
            onClick={() => playOneShot('click')}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') playOneShot('click');
            }}
        >
            <Mono size="xs" muted className="av-row__time">{formatTime(event.start)}</Mono>
            <div className="av-row__body">
                <Mono size="sm">{event.title}</Mono>
                {sub && <Mono size="xs" secondary>{sub}</Mono>}
            </div>
            {pill && (
                <Pill variant={pill.variant === 'now' ? 'err' : 'warn'}>{pill.label}</Pill>
            )}
        </div>
    );
}

// ── Compact ──────────────────────────────────────────────────────────────────

function AgendaCompact({ events }: { events: AgendaEvent[] }): ReactElement {
    const next = events[0];
    if (!next) {
        return (
            <div className="av-compact">
                <Mono size="sm" muted>Keine Termine heute</Mono>
            </div>
        );
    }
    const mins = minutesUntil(next.start);
    const sub = next.location ?? next.calendar;
    return (
        <div className="av-compact">
            <div className="av-compact__hdr">
                <span className="av-compact__dot" aria-hidden />
                <Label>NÄCHSTER</Label>
                <Mono size="xs" muted>in {mins}min</Mono>
            </div>
            <Mono size="sm">{next.title}</Mono>
            {sub && <Mono size="xs" secondary>{sub}</Mono>}
        </div>
    );
}

// ── Expanded ─────────────────────────────────────────────────────────────────

function AgendaExpanded({ events }: { events: AgendaEvent[] }): ReactElement {
    const upcoming = events.slice(0, 4);
    if (upcoming.length === 0) {
        return (
            <div className="av-expanded">
                <Mono size="sm" muted>Keine Termine in den nächsten 48 Stunden</Mono>
            </div>
        );
    }
    return (
        <div className="av-expanded">
            {upcoming.map((evt) => (
                <AgendaEventRow key={evt.id} event={evt} />
            ))}
        </div>
    );
}

// ── Entry point ──────────────────────────────────────────────────────────────

export function AgendaView({
    events: eventsProp,
    mode = 'expanded',
}: AgendaViewProps): ReactElement {
    const [liveEvents, setLiveEvents] = useState<AgendaEvent[]>([]);
    const [hasLiveData, setHasLiveData] = useState(false);
    const [backendAvailable, setBackendAvailable] = useState(true);
    const availabilityTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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

    if (eventsProp === undefined && !hasLiveData) {
        return (
            <div className="av-expanded">
                <Mono size="sm" muted>
                    {backendAvailable
                        ? 'Kalender wird geladen…'
                        : 'Kalender momentan nicht erreichbar'}
                </Mono>
            </div>
        );
    }

    return mode === 'compact' ? (
        <AgendaCompact events={list} />
    ) : (
        <AgendaExpanded events={list} />
    );
}

export default AgendaView;

