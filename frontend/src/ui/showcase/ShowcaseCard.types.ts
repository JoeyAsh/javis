import type { ReactNode } from 'react';

export interface ShowcaseCardProps {
    label: string;
    code: string;
    children: ReactNode;
    dark?: boolean;
}
