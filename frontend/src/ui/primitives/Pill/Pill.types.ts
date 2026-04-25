import type { ReactNode } from 'react';

export type PillVariant = 'default' | 'ok' | 'warn' | 'err' | 'info';

export interface PillProps {
    children: ReactNode;
    variant?: PillVariant;
    className?: string;
}
