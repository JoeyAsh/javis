import { ReactElement } from 'react';
import type { GridBackgroundProps } from './GridBackground.types';

function cn(...parts: (string | undefined | false)[]): string {
    return parts.filter(Boolean).join(' ');
}

export function GridBackground({
    drift = false,
    gridSize = 44,
    className,
}: GridBackgroundProps): ReactElement {
    return (
        <div
            aria-hidden
            className={cn(
                'fixed inset-0 pointer-events-none motion-reduce:!animation-none',
                className,
            )}
            style={{
                zIndex: 0,
                backgroundImage: [
                    `linear-gradient(rgba(76,168,232,0.04) 1px, transparent 1px)`,
                    `linear-gradient(90deg, rgba(76,168,232,0.04) 1px, transparent 1px)`,
                ].join(', '),
                backgroundSize: `${gridSize}px ${gridSize}px`,
                backgroundPosition: '-1px -1px',
                maskImage:
                    'radial-gradient(ellipse 80% 80% at 50% 50%, black 40%, transparent 100%)',
                WebkitMaskImage:
                    'radial-gradient(ellipse 80% 80% at 50% 50%, black 40%, transparent 100%)',
                animation: drift ? `jlib-grid-drift ${gridSize * 0.1}s linear infinite` : undefined,
            }}
        />
    );
}

export default GridBackground;
