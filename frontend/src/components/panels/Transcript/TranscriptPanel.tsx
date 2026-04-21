/**
 * TranscriptPanel — panel body for conversation turns.
 * Returns only body content; Window wrapper supplies chrome.
 *
 * Prototype reference: TranscriptPanel() in JARVIS HUD Hypermodern.html
 */
import { useEffect, useMemo, useRef } from 'react';
import type { ReactElement } from 'react';
import { transcriptMock } from '../../../mock/transcriptMock';
import { useTranscripts } from '../../../hooks/useTranscripts';
import type { TranscriptTurn, PanelMode } from '../../../types';
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

// ---- Expanded mode ----

function TranscriptExpanded({ turns }: { turns: TranscriptTurn[] }): ReactElement {
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [turns]);

  return (
    <div className="transcript-panel">
      {turns.map((t) => (
        <TranscriptEntry key={t.id} turn={t} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}

// ---- Props + main export ----

export interface TranscriptPanelProps {
  turns?: TranscriptTurn[];
  mode?: PanelMode;
}

/**
 * TranscriptPanel body — conversation turns with user/jarvis bubbles.
 */
export function TranscriptPanel({
  turns,
  mode = 'expanded',
}: TranscriptPanelProps): ReactElement {
  const { turns: liveTurns, isLive } = useTranscripts();
  const effectiveTurns: TranscriptTurn[] =
    turns !== undefined ? turns : isLive ? liveTurns : transcriptMock;

  return mode === 'compact' ? (
    <TranscriptCompact turns={effectiveTurns} />
  ) : (
    <TranscriptExpanded turns={effectiveTurns} />
  );
}

export default TranscriptPanel;
