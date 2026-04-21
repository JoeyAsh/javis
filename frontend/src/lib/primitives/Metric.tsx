import { ReactElement, ReactNode } from 'react';

export interface MetricProps {
    value: ReactNode;
    unit?: string;
    warn?: boolean;
    small?: boolean;
    className?: string;
}

function cn(...parts: (string | undefined | false)[]): string {
    return parts.filter(Boolean).join(' ');
}

export function Metric({
    value,
    unit,
    warn = false,
    small = false,
    className,
}: MetricProps): ReactElement {
    const valueColor = warn ? 'text-warning' : 'text-accent-bright';
    const sizeClass = small ? 'text-[12px]' : 'text-[14px]';

    return (
        <span
            className={cn('font-mono font-medium tabular-nums', sizeClass, valueColor, className)}
        >
            {value}
            {unit && <small className="text-[9px] text-text-muted ml-[2px]">{unit}</small>}
        </span>
    );
}

export default Metric;
