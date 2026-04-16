import { useMemo } from 'react';
import type { ReactElement } from 'react';
import { agendaMock } from '../../mock/agendaMock';
import type { AgendaEvent, PanelMode } from '../../types';

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

export function AgendaPanel({
  events = agendaMock,
  mode = 'expanded',
}: AgendaPanelProps): ReactElement {
  const list = useMemo<AgendaEvent[]>(() => events, [events]);
  return mode === 'compact' ? <AgendaCompact events={list} /> : <AgendaExpanded events={list} />;
}

export default AgendaPanel;
