import { useEffect, useMemo, useRef } from 'react';
import type { ReactElement } from 'react';
import { transcriptMock } from '../../mock/transcriptMock';
import type { TranscriptTurn, PanelMode } from '../../types';

export interface TranscriptPanelProps {
  turns?: TranscriptTurn[];
  mode?: PanelMode;
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function TranscriptCompact({ turns }: { turns: TranscriptTurn[] }): ReactElement {
  const lastJarvis = useMemo(
    () => [...turns].reverse().find((t) => t.role === 'jarvis'),
    [turns],
  );
  if (!lastJarvis) {
    return (
      <div className="window-compact-row" style={{ color: 'var(--text-muted)' }}>
        Kein Transcript
      </div>
    );
  }
  return (
    <>
      <div className="window-compact-row" style={{ gap: 6 }}>
        <span
          className="mono-small"
          style={{ color: 'var(--accent)', flexShrink: 0 }}
        >
          JARVIS
        </span>
        <span className="mono-small" style={{ color: 'var(--text-muted)', flexShrink: 0 }}>
          {formatTime(lastJarvis.at)}
        </span>
      </div>
      <div
        className="window-compact-row truncate"
        style={{ fontSize: 12, color: 'var(--text)' }}
        title={lastJarvis.text}
      >
        {lastJarvis.text}
      </div>
    </>
  );
}

function TranscriptExpanded({ turns }: { turns: TranscriptTurn[] }): ReactElement {
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [turns]);

  return (
    <>
      {turns.map((t) => {
        const isUser = t.role === 'user';
        return (
          <div
            key={t.id}
            style={{
              display: 'flex',
              justifyContent: isUser ? 'flex-end' : 'flex-start',
              marginBottom: 10,
            }}
          >
            <div
              style={{
                maxWidth: '82%',
                textAlign: isUser ? 'right' : 'left',
              }}
            >
              <div
                style={{
                  fontSize: 9,
                  letterSpacing: 1,
                  color: 'var(--text-muted)',
                  textTransform: 'uppercase',
                  marginBottom: 2,
                }}
              >
                {isUser ? 'You' : 'JARVIS'}
                <span style={{ marginLeft: 6, opacity: 0.7 }}>{formatTime(t.at)}</span>
              </div>
              <div
                style={{
                  fontSize: 12,
                  lineHeight: 1.5,
                  color: isUser ? 'var(--text-secondary)' : 'var(--text)',
                  background: isUser ? 'transparent' : 'rgba(76,168,232,0.05)',
                  border: isUser ? 'none' : '1px solid var(--border)',
                  borderRadius: 2,
                  padding: isUser ? '2px 0' : '6px 8px',
                  whiteSpace: 'pre-wrap',
                }}
              >
                {t.text}
              </div>
            </div>
          </div>
        );
      })}
      <div ref={bottomRef} />
    </>
  );
}

export function TranscriptPanel({
  turns = transcriptMock,
  mode = 'expanded',
}: TranscriptPanelProps): ReactElement {
  return mode === 'compact' ? (
    <TranscriptCompact turns={turns} />
  ) : (
    <TranscriptExpanded turns={turns} />
  );
}

export default TranscriptPanel;
