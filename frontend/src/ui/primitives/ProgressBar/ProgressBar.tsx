import { ReactElement } from 'react';
import { cx } from '@common/utils/cx';
import type { ProgressBarProps } from './ProgressBar.types';

const FILL_CLASSES = {
    accent: 'bg-accent shadow-glow',
    bright: 'bg-accent-bright shadow-glow',
    warn: 'bg-warning shadow-glow-warn',
} as const;

const HEIGHT_CLASSES = {
    thin: 'h-[2px]',
    normal: 'h-[4px]',
} as const;

export function ProgressBar({
    value,
    variant = 'accent',
    height = 'thin',
    className,
    'aria-label': ariaLabel,
}: ProgressBarProps): ReactElement {
    const clampedValue = Math.max(0, Math.min(1, value));
    const pct = `${(clampedValue * 100).toFixed(1)}%`;

    return (
        <div
            role="progressbar"
            aria-valuenow={Math.round(clampedValue * 100)}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={ariaLabel}
            className={cx(
                'bg-border overflow-hidden rounded-[0px]',
                HEIGHT_CLASSES[height],
                className,
            )}
        >
            <div
                className={cx(
                    'h-full transition-[width] duration-[120ms] linear',
                    FILL_CLASSES[variant],
                )}
                style={{ width: pct }}
            />
        </div>
    );
}

export default ProgressBar;
