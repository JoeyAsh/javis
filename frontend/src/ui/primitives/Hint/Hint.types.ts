import type { ReactNode } from 'react';

export interface HintKeyProps {
    children: ReactNode;
    className?: string;
}

export interface HintProps {
    children: ReactNode;
    position?: 'fixed-br' | 'inline';
    className?: string;
}
