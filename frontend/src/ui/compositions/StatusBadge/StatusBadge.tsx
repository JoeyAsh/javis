import { type ReactElement } from 'react';
import type { StatusBadgeProps, StatusBadgeState } from './StatusBadge.types';

function cn(...parts: (string | undefined | false)[]): string {
    return parts.filter(Boolean).join(' ');
}

const DOT_COLOR: Record<StatusBadgeState, string> = {
    online: 'bg-success',
    offline: 'bg-text-muted',
    warn: 'bg-warning',
};

export function StatusBadge({
    label = 'LINK · SECURE',
    state = 'online',
    pulse = true,
    className,
}: StatusBadgeProps): ReactElement {
    return (
        <span
            className={cn(
                'inline-flex items-center gap-[5px] font-mono text-[9px] uppercase tracking-[1px] text-text-secondary',
                className,
            )}
        >
            <span className="relative inline-flex items-center justify-center">
                <span
                    className={cn('block w-[6px] h-[6px] rounded-full', DOT_COLOR[state])}
                    style={
                        pulse && state === 'online'
                            ? { animation: 'jlib-status-pulse 0.9s ease-in-out infinite' }
                            : undefined
                    }
                />
            </span>
            {label}
        </span>
    );
}

export default StatusBadge;
