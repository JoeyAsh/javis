import { ReactElement } from 'react';

export interface ReticleProps {
    size?: number;
    className?: string;
    'aria-hidden'?: boolean | 'true' | 'false';
}

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
            style={{ width: size, height: size }}
        >
            {/* vertical line */}
            <span
                className="absolute bg-current"
                style={{
                    left: '50%',
                    top: 0,
                    bottom: 0,
                    width: 1,
                    transform: 'translateX(-50%)',
                }}
            />
            {/* horizontal line */}
            <span
                className="absolute bg-current"
                style={{
                    top: '50%',
                    left: 0,
                    right: 0,
                    height: 1,
                    transform: 'translateY(-50%)',
                }}
            />
        </span>
    );
}

export default Reticle;
