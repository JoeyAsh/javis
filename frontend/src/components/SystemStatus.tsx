import type { SystemStats } from '../types';

interface SystemStatusProps {
  systemStats: SystemStats | null;
  connected: boolean;
}

/**
 * System status panel showing CPU, memory, and uptime.
 */
export function SystemStatus({ systemStats, connected }: SystemStatusProps) {
  return (
    <div className="glass-panel fixed top-6 left-6 z-10 p-3">
      <div className="flex items-center gap-2 mb-3">
        <div
          className="w-2 h-2 rounded-full"
          style={{
            backgroundColor: connected ? 'var(--accent)' : '#ef4444',
          }}
        />
        <span
          className="text-xs font-medium tracking-wider"
          style={{ color: 'var(--text-secondary)' }}
        >
          {connected ? 'CONNECTED' : 'OFFLINE'}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div>
          <div
            className="text-xs font-medium mb-1"
            style={{ color: 'var(--text-muted)' }}
          >
            CPU
          </div>
          <div
            className="text-sm font-medium"
            style={{ color: 'var(--text)' }}
          >
            {systemStats ? `${Math.round(systemStats.cpu)}%` : '--'}
          </div>
        </div>

        <div>
          <div
            className="text-xs font-medium mb-1"
            style={{ color: 'var(--text-muted)' }}
          >
            MEM
          </div>
          <div
            className="text-sm font-medium"
            style={{ color: 'var(--text)' }}
          >
            {systemStats ? `${Math.round(systemStats.mem)}%` : '--'}
          </div>
        </div>

        <div>
          <div
            className="text-xs font-medium mb-1"
            style={{ color: 'var(--text-muted)' }}
          >
            UPTIME
          </div>
          <div
            className="text-sm font-medium"
            style={{ color: 'var(--text)' }}
          >
            {systemStats ? systemStats.uptime : '--'}
          </div>
        </div>
      </div>
    </div>
  );
}

export default SystemStatus;
