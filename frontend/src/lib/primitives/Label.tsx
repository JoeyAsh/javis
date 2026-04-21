import { ReactElement, ReactNode } from 'react';

export interface LabelProps {
    children: ReactNode;
    dim?: boolean;
    className?: string;
    htmlFor?: string;
}

function cn(...parts: (string | undefined | false)[]): string {
    return parts.filter(Boolean).join(' ');
}

export function Label({ children, dim = false, className, htmlFor }: LabelProps): ReactElement {
    const base = 'text-[9px] uppercase tracking-[1px] font-mono';
    const color = dim ? 'text-text-muted' : 'text-text-secondary';

    if (htmlFor) {
        return (
            <label htmlFor={htmlFor} className={cn(base, color, className)}>
                {children}
            </label>
        );
    }

    return <span className={cn(base, color, className)}>{children}</span>;
}

export default Label;
