import { type ReactElement } from 'react';
import './WaveformMeter.css';

export interface WaveformMeterProps {
    active?: boolean;
    barCount?: number;
    mirrored?: boolean;
    className?: string;
}

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
