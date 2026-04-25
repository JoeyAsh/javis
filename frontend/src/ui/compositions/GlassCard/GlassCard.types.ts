import type { ReactNode } from 'react';

export interface GlassCardProps {
    title?: string;
    children?: ReactNode;
    focused?: boolean;
    className?: string;
    bodyClassName?: string;
}
