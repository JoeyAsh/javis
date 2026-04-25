import { forwardRef } from 'react';
import type { IconProps } from './Icon.types';

const SIZE_MAP = {
    sm: 12,
    md: 14,
    lg: 16,
} as const;

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
