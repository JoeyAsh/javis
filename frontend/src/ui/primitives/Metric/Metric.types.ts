import type { ReactNode } from 'react';

export interface MetricProps {
    value: ReactNode;
    unit?: string;
    warn?: boolean;
    small?: boolean;
    className?: string;
}
