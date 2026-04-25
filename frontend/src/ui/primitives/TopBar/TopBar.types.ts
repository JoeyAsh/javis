import type { ReactNode } from 'react';

export interface TopBarProps {
    left?: ReactNode;
    center?: ReactNode;
    right?: ReactNode;
    className?: string;
}
