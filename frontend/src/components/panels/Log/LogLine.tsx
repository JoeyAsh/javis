/**
 * LogLine — a single log entry row.
 * Displays timestamp + level + module + message with severity colouring.
 * Memoized for scroll performance with large lists.
 */
import { memo, useMemo } from 'react';
import type { ReactElement } from 'react';
import type { LogLevel, LogLinePayload } from '../../../types';
import './LogPanel.css';

export interface LogLineProps {
    entry: LogLinePayload;
}

const LEVEL_COLOR: Record<LogLevel, string> = {
    DEBUG: 'var(--text-muted)',
    INFO: 'var(--text-secondary)',
    WARNING: 'var(--warning)',
    ERROR: 'var(--error)',
    CRITICAL: 'var(--error)',
};

export const LogLine = memo(function LogLine({ entry }: LogLineProps): ReactElement {
    const ts = useMemo(() => {
        const d = new Date(entry.timestamp);
        return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`;
    }, [entry.timestamp]);

    const color = LEVEL_COLOR[entry.level] ?? 'var(--text-secondary)';
    const isCritical = entry.level === 'ERROR' || entry.level === 'CRITICAL';

    return (
        <div
            style={{
                display: 'flex',
                gap: 6,
                padding: '1px 6px',
                fontFamily: 'var(--font)',
                fontSize: 10,
                lineHeight: 1.5,
                borderBottom: '1px solid rgba(26,26,46,0.4)',
                contain: 'content',
            }}
        >
            <span style={{ color: 'var(--text-muted)', flexShrink: 0, userSelect: 'none' }}>
                {ts}
            </span>
            <span
                style={{
                    color,
                    flexShrink: 0,
                    width: 52,
                    fontWeight: isCritical ? 700 : 400,
                    userSelect: 'none',
                }}
            >
                {entry.level}
            </span>
            <span
                style={{
                    color: 'var(--text-muted)',
                    flexShrink: 0,
                    maxWidth: 80,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                }}
            >
                {entry.module}
            </span>
            <span style={{ color: 'var(--text)', wordBreak: 'break-word', flex: 1 }}>
                {entry.message}
            </span>
        </div>
    );
});

export default LogLine;
