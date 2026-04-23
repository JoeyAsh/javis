import { type ReactElement } from 'react';
import type { MonoProps } from './Mono.types';

function cn(...parts: (string | undefined | false)[]): string {
    return parts.filter(Boolean).join(' ');
}

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

    return <Tag className={cn('font-mono', SIZE_CLASS[size], color, className)}>{children}</Tag>;
}

export default Mono;
