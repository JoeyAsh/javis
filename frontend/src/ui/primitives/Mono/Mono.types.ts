import type { ReactNode, ElementType } from 'react';

export type MonoSize = 'xs' | 'sm' | 'md' | 'lg';

export interface MonoProps {
    children: ReactNode;
    size?: MonoSize;
    className?: string;
    as?: ElementType;
    muted?: boolean;
    secondary?: boolean;
}
