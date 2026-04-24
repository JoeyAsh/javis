import { type ReactElement } from 'react';
import type { WaveStripProps } from './WaveStrip.types';

export function WaveStrip({
    active = true,
    mirrored = false,
    className,
}: WaveStripProps): ReactElement {
    const classes = ['lib-wave-strip', !active && 'inactive', mirrored && 'mirrored', className]
        .filter(Boolean)
        .join(' ');

    return (
        <span className={classes} aria-hidden="true">
            {Array.from({ length: 7 }, (_, i) => (
                <i key={i} className="lib-wave-strip__bar" />
            ))}
        </span>
    );
}

export default WaveStrip;
