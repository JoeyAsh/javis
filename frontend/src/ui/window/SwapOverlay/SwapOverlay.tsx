import type { CSSProperties, ReactElement } from 'react';
import type { SwapOverlayProps } from './SwapOverlay.types';

export function SwapOverlay({
    active,
    ghostRect,
    hovered = false,
    className,
}: SwapOverlayProps): ReactElement {
    const rootCls = ['lib-swap', className].filter(Boolean).join(' ');

    if (!active || ghostRect === null) {
        return <div className={rootCls} aria-hidden />;
    }

    const style: CSSProperties = {
        left: ghostRect.x,
        top: ghostRect.y,
        width: ghostRect.w,
        height: ghostRect.h,
    };

    const ghostCls = ['lib-swap__ghost', hovered ? 'lib-swap__ghost--hovered' : '']
        .filter(Boolean)
        .join(' ');

    return (
        <div className={rootCls} aria-hidden>
            <div className={ghostCls} style={style} />
        </div>
    );
}

export default SwapOverlay;
