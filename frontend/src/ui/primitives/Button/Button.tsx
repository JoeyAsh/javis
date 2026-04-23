import { forwardRef } from 'react';
import { useClickSfx, useHoverSfx } from '@core/audio';
import type { ButtonProps } from './Button.types';

function cn(...parts: (string | undefined | false)[]): string {
    return parts.filter(Boolean).join(' ');
}

const VARIANT_CLASSES = {
    primary:
        'bg-accent text-bg border-accent hover:bg-accent-bright hover:border-accent-bright hover:shadow-glow-strong',
    secondary:
        'bg-transparent text-accent border-accent hover:text-accent-bright hover:border-accent-bright hover:shadow-glow',
    ghost: 'bg-transparent text-text-secondary border-border hover:border-accent hover:text-accent',
    danger: 'bg-transparent text-error border-error hover:bg-error hover:text-bg hover:shadow-glow-error',
} as const;

const SIZE_CLASSES = {
    sm: 'text-[10px] px-[10px] py-[4px]',
    md: 'text-[11px] px-[14px] py-[6px]',
} as const;

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
    { variant = 'secondary', size = 'md', className, children, onClick, ...rest },
    ref,
) {
    const hoverSfx = useHoverSfx('button');
    const clickSfx = useClickSfx(onClick);

    return (
        <button
            ref={ref}
            className={cn(
                'font-mono uppercase tracking-[1px] border rounded-[2px] cursor-pointer',
                'transition-all duration-[200ms]',
                'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent',
                'disabled:opacity-40 disabled:cursor-not-allowed disabled:pointer-events-none',
                'active:brightness-110',
                VARIANT_CLASSES[variant],
                SIZE_CLASSES[size],
                className,
            )}
            onMouseEnter={hoverSfx}
            onClick={clickSfx}
            data-sfx-hover="button"
            {...rest}
        >
            {children}
        </button>
    );
});

Button.displayName = 'Button';

export default Button;
