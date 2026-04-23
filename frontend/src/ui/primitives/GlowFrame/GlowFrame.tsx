import { ReactElement } from 'react';
import type { GlowFrameProps } from './GlowFrame.types';

function cn(...parts: (string | undefined | false)[]): string {
    return parts.filter(Boolean).join(' ');
}

export function GlowFrame({
    children,
    breathe = false,
    strong = false,
    className,
}: GlowFrameProps): ReactElement {
    const staticShadow = strong ? 'var(--glow-strong)' : 'var(--glow)';

    return (
        <div
            className={cn('border border-border rounded-[2px]', className)}
            style={{
                boxShadow: breathe ? undefined : staticShadow,
                animation: breathe
                    ? 'jlib-glow-breathe 2.8s cubic-bezier(.4,0,.2,1) infinite'
                    : undefined,
                borderColor: 'var(--accent-dim)',
            }}
        >
            {children}
        </div>
    );
}

export default GlowFrame;
