import type { OrbState } from '../types';

interface StatusBarProps {
  orbState: OrbState;
  language?: string;
}

const STATE_LABELS: Record<OrbState, string> = {
  idle: 'STANDBY',
  listening: 'LISTENING',
  thinking: 'PROCESSING',
  speaking: 'RESPONDING',
};

/**
 * Status bar showing current orb state and language indicator.
 */
export function StatusBar({ orbState, language = 'EN' }: StatusBarProps) {
  return (
    <div className="glass-panel fixed bottom-6 left-6 z-10 px-4 py-2 flex items-center gap-4">
      <div className="flex items-center gap-2">
        <div
          className="w-2 h-2 rounded-full transition-colors duration-300"
          style={{
            backgroundColor:
              orbState === 'idle'
                ? 'var(--text-muted)'
                : orbState === 'thinking'
                  ? 'var(--accent-bright)'
                  : orbState === 'speaking'
                    ? 'var(--accent-speak)'
                    : 'var(--accent)',
            boxShadow:
              orbState !== 'idle' ? '0 0 8px currentColor' : 'none',
          }}
        />
        <span
          className="text-sm font-medium tracking-wider transition-all duration-300"
          style={{ color: 'var(--text)' }}
        >
          {STATE_LABELS[orbState]}
        </span>
      </div>
      <div
        className="text-xs font-medium px-2 py-0.5"
        style={{
          color: 'var(--text-secondary)',
          borderLeft: '1px solid var(--border)',
          paddingLeft: '1rem',
        }}
      >
        {language.toUpperCase()}
      </div>
    </div>
  );
}
