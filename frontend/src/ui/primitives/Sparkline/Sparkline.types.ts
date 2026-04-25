export type SparklineVariant = 'accent' | 'warn';

export interface SparklineProps {
    data: number[];
    variant?: SparklineVariant;
    width?: number;
    height?: number;
    className?: string;
    'aria-label'?: string;
}
