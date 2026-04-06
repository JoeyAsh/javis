import type { TranscriptEntry } from '../types';

interface TranscriptFeedProps {
  transcript: TranscriptEntry[];
}

/**
 * Transcript feed showing recent conversation exchanges.
 */
export function TranscriptFeed({ transcript }: TranscriptFeedProps) {
  if (transcript.length === 0) {
    return null;
  }

  return (
    <div
      className="glass-panel fixed bottom-20 left-6 z-10 p-4 max-w-[420px]"
      style={{ maxHeight: '300px', overflowY: 'auto' }}
    >
      <div className="flex flex-col gap-3">
        {transcript.map((entry) => (
          <div
            key={entry.id}
            className={`flex flex-col fade-in ${
              entry.role === 'user' ? 'items-end' : 'items-start'
            }`}
          >
            <div
              className="text-xs font-medium mb-1"
              style={{
                color:
                  entry.role === 'user'
                    ? 'var(--accent)'
                    : 'var(--text-secondary)',
              }}
            >
              {entry.role === 'user' ? '>' : 'J.'}
            </div>
            <div
              className="text-sm leading-relaxed"
              style={{
                color:
                  entry.role === 'user' ? 'var(--accent)' : 'var(--text)',
                textAlign: entry.role === 'user' ? 'right' : 'left',
              }}
            >
              {entry.text}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default TranscriptFeed;
