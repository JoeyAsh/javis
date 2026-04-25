import { ReactElement } from 'react';
import { cx } from '@common/utils/cx';
import type { MetricProps } from './Metric.types';

export function Metric({
    value,
    unit,
    warn = false,
    small = false,
    className,
}: MetricProps): ReactElement {
    const valueColor = warn ? 'text-warning' : 'text-accent-bright';
    const sizeClass = small ? 'text-[12px]' : 'text-[14px]';

    return (
        <span
            className={cx('font-mono font-medium tabular-nums', sizeClass, valueColor, className)}
        >
            {value}
            {unit && <small className="text-[9px] text-text-muted ml-[2px]">{unit}</small>}
        </span>
    );
}

export default Metric;
