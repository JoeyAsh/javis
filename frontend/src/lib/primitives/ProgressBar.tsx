import { ReactElement } from 'react';

export type ProgressBarVariant = 'accent' | 'bright' | 'warn';
export type ProgressBarHeight = 'thin' | 'normal';

export interface ProgressBarProps {
    value: number;
    variant?: ProgressBarVariant;
    height?: ProgressBarHeight;
    className?: string;
    'aria-label'?: string;
}

function cn(...parts: (string | undefined | false)[]): string {
    return parts.filter(Boolean).join(' ');
}

const FILL_CLASSES: Record<ProgressBarVariant, string> = {
    accent: 'bg-accent shadow-glow',
    bright: 'bg-accent-bright shadow-glow',
    warn: 'bg-warning shadow-glow-warn',
};

const HEIGHT_CLASSES: Record<ProgressBarHeight, string> = {
    thin: 'h-[2px]',
    normal: 'h-[4px]',
};

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
            className={cn(
                'bg-border overflow-hidden rounded-[0px]',
                HEIGHT_CLASSES[height],
                className,
            )}
        >
            <div
                className={cn(
                    'h-full transition-[width] duration-[120ms] linear',
                    FILL_CLASSES[variant],
                )}
                style={{ width: pct }}
            />
        </div>
    );
}

export default ProgressBar;
