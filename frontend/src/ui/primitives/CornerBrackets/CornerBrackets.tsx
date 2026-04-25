import { CSSProperties, ReactElement } from 'react';
import { cx } from '@common/utils/cx';
import type { CornerBracketsProps } from './CornerBrackets.types';

export function CornerBrackets({
    focused = false,
    size = 12,
    children,
    className,
}: CornerBracketsProps): ReactElement {
    const cornerBase: CSSProperties = {
        position: 'absolute',
        width: size,
        height: size,
        borderColor: focused ? 'var(--accent-bright)' : 'var(--accent)',
        borderStyle: 'solid',
        opacity: focused ? 1 : 0.7,
        pointerEvents: 'none',
        transition: 'border-color 200ms, opacity 200ms',
    };

    return (
        <div className={cx('relative', className)}>
            {/* top-left */}
            <span
                aria-hidden
                style={{ ...cornerBase, top: -2, left: -2, borderWidth: '1px 0 0 1px' }}
            />
            {/* top-right */}
            <span
                aria-hidden
                style={{ ...cornerBase, top: -2, right: -2, borderWidth: '1px 1px 0 0' }}
            />
            {/* bottom-left */}
            <span
                aria-hidden
                style={{ ...cornerBase, bottom: -2, left: -2, borderWidth: '0 0 1px 1px' }}
            />
            {/* bottom-right */}
            <span
                aria-hidden
                style={{ ...cornerBase, bottom: -2, right: -2, borderWidth: '0 1px 1px 0' }}
            />
            {children}
        </div>
    );
}

export default CornerBrackets;
