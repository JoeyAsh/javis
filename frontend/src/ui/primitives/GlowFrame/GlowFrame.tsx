import { ReactElement } from 'react';
import { cx } from '@common/utils/cx';
import type { GlowFrameProps } from './GlowFrame.types';

export function GlowFrame({
    children,
    breathe = false,
    strong = false,
    className,
}: GlowFrameProps): ReactElement {
    const staticShadow = strong ? 'var(--glow-strong)' : 'var(--glow)';

    return (
        <div
            className={cx('border border-[var(--accent-dim)] rounded-[2px]', className)}
            style={{
                boxShadow: breathe ? undefined : staticShadow,
                animation: breathe
                    ? 'jlib-glow-breathe 2.8s cubic-bezier(.4,0,.2,1) infinite'
                    : undefined,
            } as React.CSSProperties}
        >
            {children}
        </div>
    );
}

export default GlowFrame;
