/**
 * TranscriptPanel — panel body for conversation turns.
 * Returns only body content; Window wrapper supplies chrome.
 *
 * Prototype reference: TranscriptPanel() in JARVIS HUD Hypermodern.html
 */
import { useEffect, useMemo, useRef } from 'react';
import type { CSSProperties, ReactElement } from 'react';
import { transcriptMock } from '../../../mock/transcriptMock';
import { useTranscripts } from '../../../hooks/useTranscripts';
import type { AppOrbState, TranscriptTurn, PanelMode } from '../../../types';
import { TranscriptEntry } from './TranscriptEntry';
import './TranscriptPanel.css';

// ---- Compact mode ----

function TranscriptCompact({ turns }: { turns: TranscriptTurn[] }): ReactElement {
  const lastJarvis = useMemo(
    () => [...turns].reverse().find((t) => t.role === 'jarvis'),
    [turns],
  );
  if (!lastJarvis) {
    return (
      <div className="transcript-compact">
        <span className="transcript-empty">Kein Transcript</span>
      </div>
    );
  }
  const hrs = new Date(lastJarvis.at).getHours();
  const mins = new Date(lastJarvis.at).getMinutes();
  const time = `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}`;
  return (
    <div className="transcript-compact">
      <div className="transcript-compact__header">
        <span className="transcript-compact__role">JARVIS</span>
        <span className="transcript-compact__time">{time}</span>
      </div>
      <div className="transcript-compact__text" title={lastJarvis.text}>
        {lastJarvis.text}
      </div>
    </div>
  );
}

// Thinking dots — 3 blinking circles matching prototype blink 1.2s pattern.
const dotStyle: CSSProperties = {
  width: 4,
  height: 4,
  background: 'var(--accent)',
  borderRadius: '50%',
  display: 'inline-block',
};

function ThinkingDots(): ReactElement {
  return (
    <div className="transcript-turn transcript-turn--jarvis">
      <div className="transcript-turn__block">
        <div className="transcript-turn__meta">
          <span className="transcript-turn__meta-role">J.</span>
          <span className="transcript-turn__meta-time">…</span>
        </div>
        <div className="transcript-turn__bubble--jarvis">
          <span style={{ display: 'inline-flex', gap: 3 }}>
            <i style={{ ...dotStyle, animation: 'blink 1.2s ease-in-out infinite' }} />
            <i style={{ ...dotStyle, animation: 'blink 1.2s ease-in-out infinite 0.2s' }} />
            <i style={{ ...dotStyle, animation: 'blink 1.2s ease-in-out infinite 0.4s' }} />
          </span>
        </div>
      </div>
    </div>
  );
}

// ---- Expanded mode ----

function TranscriptExpanded({
  turns,
  orbState,
}: {
  turns: TranscriptTurn[];
  orbState: AppOrbState;
}): ReactElement {
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [turns, orbState]);

  return (
    <div className="transcript-panel">
      {turns.map((t) => (
        <TranscriptEntry key={t.id} turn={t} />
      ))}
      {orbState === 'thinking' && <ThinkingDots />}
      <div ref={bottomRef} />
    </div>
  );
}

// ---- Props + main export ----

export interface TranscriptPanelProps {
  turns?: TranscriptTurn[];
  mode?: PanelMode;
  orbState?: AppOrbState;
}

/**
 * TranscriptPanel body — conversation turns with user/jarvis bubbles.
 * When orbState is 'thinking', shows blinking dots turn matching prototype.
 */
export function TranscriptPanel({
  turns,
  mode = 'expanded',
  orbState = 'idle',
}: TranscriptPanelProps): ReactElement {
  const { turns: liveTurns, isLive } = useTranscripts();
  const effectiveTurns: TranscriptTurn[] =
    turns !== undefined ? turns : isLive ? liveTurns : transcriptMock;

  return mode === 'compact' ? (
    <TranscriptCompact turns={effectiveTurns} />
  ) : (
    <TranscriptExpanded turns={effectiveTurns} orbState={orbState} />
  );
}

export default TranscriptPanel;
