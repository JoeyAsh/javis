import { useEffect, useMemo, useState } from 'react';
import type { ReactElement } from 'react';
import type { AgendaEvent, CalendarStatePayload, PanelMode } from '../../types';
import { subscribeCalendarStateStream } from '../../hooks/useWebSocket';

export interface AgendaPanelProps {
  events?: AgendaEvent[];
  mode?: PanelMode;
}

function formatTimeRange(startISO: string, endISO: string): string {
  const start = new Date(startISO);
  const end = new Date(endISO);
  const fmt = (d: Date): string =>
    `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  return `${fmt(start)} — ${fmt(end)}`;
}

function durationMinutes(startISO: string, endISO: string): number {
  return Math.round((new Date(endISO).getTime() - new Date(startISO).getTime()) / 60_000);
}

function minutesUntil(iso: string): number {
  return Math.max(0, Math.round((new Date(iso).getTime() - Date.now()) / 60_000));
}

function AgendaCompact({ events }: { events: AgendaEvent[] }): ReactElement {
  const next = events[0];
  if (!next) {
    return (
      <div className="window-compact-row" style={{ color: 'var(--text-muted)' }}>
        Keine Termine heute
      </div>
    );
  }
  const mins = minutesUntil(next.start);
  return (
    <>
      <div className="window-compact-row" style={{ color: 'var(--accent-bright)' }}>
        <span
          aria-hidden
          style={{
            display: 'inline-block',
            width: 4,
            height: 4,
            background: 'var(--accent)',
            borderRadius: '50%',
            flexShrink: 0,
          }}
        />
        <span className="mono-small" style={{ color: 'var(--accent)' }}>
          NÄCHSTER
        </span>
        <span className="mono-small" style={{ marginLeft: 'auto' }}>
          in {mins}min
        </span>
      </div>
      <div className="window-compact-row truncate" style={{ fontSize: 13, color: 'var(--text)' }}>
        {next.title}
      </div>
      <div
        className="window-compact-row truncate"
        style={{ fontSize: 10, color: 'var(--text-muted)' }}
      >
        {next.location ?? next.calendar}
      </div>
    </>
  );
}

function AgendaExpanded({ events }: { events: AgendaEvent[] }): ReactElement {
  const upcoming = events.slice(0, 4);
  if (upcoming.length === 0) {
    return (
      <div className="list-item" style={{ color: 'var(--text-muted)', fontSize: 13 }}>
        Keine Termine in den nächsten 48 Stunden
      </div>
    );
  }
  return (
    <>
      {upcoming.map((evt, idx) => (
        <div className="list-item" key={evt.id}>
          <div
            style={{
              display: 'flex',
              alignItems: 'baseline',
              gap: 8,
              marginBottom: 4,
            }}
          >
            <span
              style={{
                fontSize: 11,
                color: 'var(--accent-bright)',
                letterSpacing: 1,
              }}
            >
              {formatTimeRange(evt.start, evt.end)}
            </span>
            <span className="mono-small" style={{ marginLeft: 'auto' }}>
              {durationMinutes(evt.start, evt.end)}min
            </span>
          </div>
          <div style={{ fontSize: 13, color: 'var(--text)', marginBottom: 2 }}>{evt.title}</div>
          <div
            style={{
              fontSize: 10,
              color: 'var(--text-muted)',
              display: 'flex',
              justifyContent: 'space-between',
            }}
          >
            <span>{evt.location ?? evt.calendar}</span>
            {idx < upcoming.length - 1 && <span>→ {evt.minutesToNext ?? 0}min gap</span>}
          </div>
        </div>
      ))}
    </>
  );
}

/**
 * AgendaPanel — renders upcoming calendar events from live WebSocket state.
 *
 * Accepts an optional `events` prop for testing / initial render. If no prop
 * is supplied, subscribes to `calendar_state` WebSocket messages and updates
 * in real time. Uses live data only — no static mock imports.
 */
export function AgendaPanel({
  events: eventsProp,
  mode = 'expanded',
}: AgendaPanelProps): ReactElement {
  const [liveEvents, setLiveEvents] = useState<AgendaEvent[]>([]);
  const [hasLiveData, setHasLiveData] = useState(false);

  useEffect(() => {
    // If events are provided as a prop (e.g. tests), skip subscription.
    if (eventsProp !== undefined) return;

    const unsub = subscribeCalendarStateStream((payload: CalendarStatePayload) => {
      setLiveEvents(payload.events);
      setHasLiveData(true);
    });
    return unsub;
  }, [eventsProp]);

  const list = useMemo<AgendaEvent[]>(() => {
    if (eventsProp !== undefined) return eventsProp;
    return liveEvents;
  }, [eventsProp, liveEvents]);

  // While waiting for first live push (< 2s typically), show compact loading state
  if (eventsProp === undefined && !hasLiveData) {
    return (
      <div className="window-compact-row" style={{ color: 'var(--text-muted)', fontSize: 11 }}>
        Kalender wird geladen…
      </div>
    );
  }

  return mode === 'compact' ? <AgendaCompact events={list} /> : <AgendaExpanded events={list} />;
}

export default AgendaPanel;
