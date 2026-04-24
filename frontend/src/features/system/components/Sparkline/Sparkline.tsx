import { useMemo } from 'react';
import type { ReactElement } from 'react';
import type { SparklineProps } from './Sparkline.types';

export function Sparkline({ values, color, warn = false }: SparklineProps): ReactElement {
    const { path, fill } = useMemo(() => {
        const w = 100;
        const h = 28;
        if (values.length === 0) return { path: '', fill: '' };
        const max = Math.max(...values, 1);
        const step = w / Math.max(values.length - 1, 1);
        const pts = values.map((v, i) => {
            const x = i * step;
            const y = h - (v / max) * h;
            return `${x.toFixed(2)},${y.toFixed(2)}`;
        });
        const line = `M ${pts.join(' L ')}`;
        const area = `${line} L ${w},${h} L 0,${h} Z`;
        return { path: line, fill: area };
    }, [values]);

    const c = warn ? 'var(--warning)' : color;
    const gradId = `spark-${c.replace(/[^a-z0-9]/gi, '')}-${warn ? 'w' : 'n'}`;

    return (
        <svg
            viewBox="0 0 100 28"
            preserveAspectRatio="none"
            className="w-full h-7 block"
            aria-hidden
        >
            <defs>
                <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={c} stopOpacity="0.5" />
                    <stop offset="100%" stopColor={c} stopOpacity="0" />
                </linearGradient>
            </defs>
            {fill && <path d={fill} fill={`url(#${gradId})`} />}
            {path && <path d={path} fill="none" stroke={c} strokeWidth="1.3" />}
        </svg>
    );
}

export default Sparkline;
