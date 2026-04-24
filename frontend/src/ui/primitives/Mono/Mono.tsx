import { type ReactElement } from 'react';
import { cx } from '@common/utils/cx';
import type { MonoProps } from './Mono.types';

const SIZE_CLASS = {
    xs: 'text-[9px]',
    sm: 'text-[10px]',
    md: 'text-[11px]',
    lg: 'text-[13px]',
} as const;

export function Mono({
    children,
    size = 'md',
    className,
    as: Tag = 'span',
    muted = false,
    secondary = false,
}: MonoProps): ReactElement {
    const color = muted ? 'text-text-muted' : secondary ? 'text-text-secondary' : 'text-text';

    return <Tag className={cx('font-mono', SIZE_CLASS[size], color, className)}>{children}</Tag>;
}

export default Mono;
