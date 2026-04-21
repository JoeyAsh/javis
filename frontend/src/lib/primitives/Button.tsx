import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: ButtonVariant;
    size?: ButtonSize;
    className?: string;
    children: ReactNode;
}

function cn(...parts: (string | undefined | false)[]): string {
    return parts.filter(Boolean).join(' ');
}

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
    primary:
        'bg-accent text-bg border-accent hover:bg-accent-bright hover:border-accent-bright hover:shadow-glow-strong',
    secondary:
        'bg-transparent text-accent border-accent hover:text-accent-bright hover:border-accent-bright hover:shadow-glow',
    ghost: 'bg-transparent text-text-secondary border-border hover:border-accent hover:text-accent',
    danger: 'bg-transparent text-error border-error hover:bg-error hover:text-bg hover:shadow-glow-error',
};

const SIZE_CLASSES: Record<ButtonSize, string> = {
    sm: 'text-[10px] px-[10px] py-[4px]',
    md: 'text-[11px] px-[14px] py-[6px]',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
    { variant = 'secondary', size = 'md', className, children, ...rest },
    ref,
) {
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
            {...rest}
        >
            {children}
        </button>
    );
});

Button.displayName = 'Button';

export default Button;
