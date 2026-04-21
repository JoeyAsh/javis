/**
 * TranscriptEntry — single conversation turn.
 * Matches prototype `.turn .blk .meta / .bub` pattern.
 */
import type { ReactElement } from 'react';
import type { TranscriptTurn } from '../../../types';
import './TranscriptPanel.css';

function formatTime(iso: string): string {
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

export interface TranscriptEntryProps {
  turn: TranscriptTurn;
}

export function TranscriptEntry({ turn }: TranscriptEntryProps): ReactElement {
  const isUser = turn.role === 'user';
  const rowClass = `transcript-turn ${isUser ? 'transcript-turn--user' : 'transcript-turn--jarvis'}`;
  const bubbleClass = isUser
    ? 'transcript-turn__bubble--user'
    : 'transcript-turn__bubble--jarvis';

  return (
    <div className={rowClass}>
      <div className="transcript-turn__block">
        <div className="transcript-turn__meta">
          {!isUser && (
            <span className="transcript-turn__meta-role">J.</span>
          )}
          {isUser ? 'You ' : ''}
          <span className="transcript-turn__meta-time">{formatTime(turn.at)}</span>
        </div>
        <div className={bubbleClass}>{turn.text}</div>
      </div>
    </div>
  );
}

export default TranscriptEntry;
