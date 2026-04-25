import { ReactElement } from 'react';
import { cx } from '@common/utils/cx';
import type { LabelProps } from './Label.types';

export function Label({ children, dim = false, className, htmlFor }: LabelProps): ReactElement {
    const base = 'text-[9px] uppercase tracking-[1px] font-mono';
    const color = dim ? 'text-text-muted' : 'text-text-secondary';

    if (htmlFor) {
        return (
            <label htmlFor={htmlFor} className={cx(base, color, className)}>
                {children}
            </label>
        );
    }

    return <span className={cx(base, color, className)}>{children}</span>;
}

export default Label;
