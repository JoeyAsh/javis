import type { ReactNode } from 'react';

export interface LabelProps {
    children: ReactNode;
    dim?: boolean;
    className?: string;
    htmlFor?: string;
}
