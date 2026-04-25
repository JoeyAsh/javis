export type ProgressBarVariant = 'accent' | 'bright' | 'warn';
export type ProgressBarHeight = 'thin' | 'normal';

export interface ProgressBarProps {
    value: number;
    variant?: ProgressBarVariant;
    height?: ProgressBarHeight;
    className?: string;
    'aria-label'?: string;
}
