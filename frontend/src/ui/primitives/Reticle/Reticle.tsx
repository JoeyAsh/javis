import { ReactElement } from 'react';
import type { ReticleProps } from './Reticle.types';

function cn(...parts: (string | undefined | false)[]): string {
    return parts.filter(Boolean).join(' ');
}

export function Reticle({
    size = 12,
    className,
    'aria-hidden': ariaHidden = true,
}: ReticleProps): ReactElement {
    return (
        <span
            role="presentation"
            aria-hidden={ariaHidden}
            className={cn('relative inline-block text-accent', className)}
            style={{ width: size, height: size } as React.CSSProperties}
        >
            {/* vertical line */}
            <span className="absolute bg-current left-1/2 top-0 bottom-0 w-px -translate-x-1/2" />
            {/* horizontal line */}
            <span className="absolute bg-current top-1/2 left-0 right-0 h-px -translate-y-1/2" />
        </span>
    );
}

export default Reticle;
