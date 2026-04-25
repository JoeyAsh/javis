import { ReactElement } from 'react';
import { cx } from '@common/utils/cx';
import type { SparklineProps } from './Sparkline.types';
import { buildPath } from './utils';

const STROKE_COLOR = {
    accent: '#6ec4ff',
    warn: '#e8b24c',
} as const;

const FILL_OPACITY = {
    accent: '0.15',
    warn: '0.18',
} as const;

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
            className={cx('block w-full', className)}
            style={{ height: `${height}px` } as React.CSSProperties}
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
