import { ReactElement, ReactNode } from 'react';

export type PillVariant = 'default' | 'ok' | 'warn' | 'err' | 'info';

export interface PillProps {
    children: ReactNode;
    variant?: PillVariant;
    className?: string;
}

function cn(...parts: (string | undefined | false)[]): string {
    return parts.filter(Boolean).join(' ');
}

const VARIANT_CLASSES: Record<PillVariant, string> = {
    default: 'text-text-secondary border-border',
    ok: 'text-success border-[rgba(76,232,138,0.4)]',
    warn: 'text-warning border-[rgba(232,168,76,0.4)]',
    err: 'text-error border-[rgba(232,76,76,0.4)]',
    info: 'text-accent-bright border-[rgba(126,200,255,0.4)]',
};

export function Pill({ children, variant = 'default', className }: PillProps): ReactElement {
    return (
        <span
            className={cn(
                'inline-flex items-center px-[6px] py-[2px]',
                'text-[9px] uppercase tracking-[1px] font-mono',
                'border rounded-[2px]',
                VARIANT_CLASSES[variant],
                className,
            )}
        >
            {children}
        </span>
    );
}

export default Pill;
