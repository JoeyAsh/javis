import { type ReactElement, type ReactNode, type ElementType } from 'react';

export type MonoSize = 'xs' | 'sm' | 'md' | 'lg';

export interface MonoProps {
    children: ReactNode;
    size?: MonoSize;
    className?: string;
    as?: ElementType;
    muted?: boolean;
    secondary?: boolean;
}

function cn(...parts: (string | undefined | false)[]): string {
    return parts.filter(Boolean).join(' ');
}

const SIZE_CLASS: Record<MonoSize, string> = {
    xs: 'text-[9px]',
    sm: 'text-[10px]',
    md: 'text-[11px]',
    lg: 'text-[13px]',
};

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
