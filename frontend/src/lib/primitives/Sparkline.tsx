import { ReactElement } from 'react';

export type SparklineVariant = 'accent' | 'warn';

export interface SparklineProps {
    data: number[];
    variant?: SparklineVariant;
    width?: number;
    height?: number;
    className?: string;
    'aria-label'?: string;
}

function cn(...parts: (string | undefined | false)[]): string {
    return parts.filter(Boolean).join(' ');
}

const STROKE_COLOR: Record<SparklineVariant, string> = {
    accent: '#6ec4ff',
    warn: '#e8b24c',
};

const FILL_OPACITY: Record<SparklineVariant, string> = {
    accent: '0.15',
    warn: '0.18',
};

function buildPath(data: number[], vw: number, vh: number): string {
    if (data.length < 2) return '';
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;
    const pad = 2;
    const points = data.map((v, i) => {
        const x = (i / (data.length - 1)) * vw;
        const y = vh - pad - ((v - min) / range) * (vh - pad * 2);
        return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
    });
    return points.join(' ');
}

export function Sparkline({
    data,
    variant = 'accent',
    width = 100,
    height = 28,
    className,
    'aria-label': ariaLabel,
}: SparklineProps): ReactElement {
    const stroke = STROKE_COLOR[variant];
    const fillOpacity = FILL_OPACITY[variant];
    const linePath = buildPath(data, width, height);

    // Close the fill path at the bottom
    let fillPath = '';
    if (linePath) {
        fillPath = `${linePath} L${width},${height} L0,${height} Z`;
    }

    return (
        <svg
            viewBox={`0 0 ${width} ${height}`}
            preserveAspectRatio="none"
            className={cn('block', className)}
            style={{ width: '100%', height: `${height}px` }}
            aria-label={ariaLabel}
            role={ariaLabel ? 'img' : undefined}
        >
            {linePath && (
                <>
                    <path d={fillPath} fill={stroke} opacity={fillOpacity} />
                    <path d={linePath} stroke={stroke} strokeWidth="1.2" fill="none" />
                </>
            )}
        </svg>
    );
}

export default Sparkline;
