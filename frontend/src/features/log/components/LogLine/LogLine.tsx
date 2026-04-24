import { memo, useMemo } from 'react';
import type { ReactElement } from 'react';
import type { LogLevel } from '../../types';
import type { LogLineProps } from './LogLine.types';

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
        <div className="flex gap-[6px] py-[1px] px-[6px] font-mono text-[10px] leading-[1.5] border-b border-[rgba(26,26,46,0.4)] [contain:content]">
            <span className="text-[var(--text-muted)] shrink-0 select-none">
                {ts}
            </span>
            <span
                className="shrink-0 w-[52px] select-none"
                style={{
                    color,
                    fontWeight: isCritical ? 700 : 400,
                } as React.CSSProperties}
            >
                {entry.level}
            </span>
            <span className="text-[var(--text-muted)] shrink-0 max-w-[80px] overflow-hidden text-ellipsis whitespace-nowrap">
                {entry.module}
            </span>
            <span className="text-[var(--text)] break-words flex-1">
                {entry.message}
            </span>
        </div>
    );
});

export default LogLine;
