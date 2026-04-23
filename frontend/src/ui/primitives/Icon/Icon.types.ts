import type { LucideIcon } from 'lucide-react';

export type IconSize = 'sm' | 'md' | 'lg';

export interface IconProps {
    icon: LucideIcon;
    size?: IconSize;
    className?: string;
    'aria-label'?: string;
    'aria-hidden'?: boolean | 'true' | 'false';
}
