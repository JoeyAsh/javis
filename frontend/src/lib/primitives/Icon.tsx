import { forwardRef } from 'react';
import type { LucideIcon } from 'lucide-react';

export type IconSize = 'sm' | 'md' | 'lg';

export interface IconProps {
    icon: LucideIcon;
    size?: IconSize;
    className?: string;
    'aria-label'?: string;
    'aria-hidden'?: boolean | 'true' | 'false';
}

const SIZE_MAP: Record<IconSize, number> = {
    sm: 12,
    md: 14,
    lg: 16,
};

export const Icon = forwardRef<SVGSVGElement, IconProps>(function Icon(
    {
        icon: LucideIconComponent,
        size = 'md',
        className = '',
        'aria-label': ariaLabel,
        'aria-hidden': ariaHidden,
    },
    ref,
) {
    const px = SIZE_MAP[size];
    return (
        <LucideIconComponent
            ref={ref}
            width={px}
            height={px}
            strokeWidth={1.75}
            className={className}
            aria-label={ariaLabel}
            aria-hidden={ariaHidden}
        />
    );
});

Icon.displayName = 'Icon';

export default Icon;
