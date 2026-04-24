import { type ReactElement } from 'react';
import type { WaveformMeterProps } from './WaveformMeter.types';

export function WaveformMeter({
    active = true,
    barCount = 12,
    mirrored = false,
    className,
}: WaveformMeterProps): ReactElement {
    const classes = ['lib-meter', !active && 'inactive', mirrored && 'mirrored', className]
        .filter(Boolean)
        .join(' ');

    return (
        <div className={classes} aria-hidden="true">
            {Array.from({ length: barCount }, (_, i) => (
                <i key={i} className="lib-meter__bar" />
            ))}
        </div>
    );
}

export default WaveformMeter;
