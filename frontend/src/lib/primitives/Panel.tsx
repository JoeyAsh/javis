import {
    type CSSProperties,
    type ReactNode,
    type MouseEvent,
    type ReactElement,
    type Ref,
    type PointerEventHandler,
} from 'react';
import { useHoverSfx } from '../audio/hooks';
import './Panel.css';

export interface PanelProps {
    ix?: ReactNode;
    title?: ReactNode;
    badge?: ReactNode;
    /** Optional action button cluster rendered at the right edge of the header. */
    actions?: ReactNode;
    focused?: boolean;
    onFocus?: () => void;
    className?: string;
    style?: CSSProperties;
    children?: ReactNode;
    /**
     * When provided, attached to the `.lib-panel__hdr` element so the caller
     * can imperatively bind drag handlers (e.g. via useDraggable).
     */
    headerRef?: Ref<HTMLDivElement>;
    /**
     * Called on `pointerdown` on the entire header element. Used by Window to
     * make the full header the drag handle.
     */
    onHeaderPointerDown?: PointerEventHandler<HTMLDivElement>;
    /**
     * Called on `click` on the header element (bubbles from children).
     * Used by Window for double-click mode-toggle detection.
     */
    onHeaderClick?: (e: MouseEvent<HTMLDivElement>) => void;
}

function cn(...parts: (string | undefined | false)[]): string {
    return parts.filter(Boolean).join(' ');
}

export function Panel({
    ix,
    title,
    badge,
    actions,
    focused = false,
    onFocus,
    className,
    style,
    children,
    headerRef,
    onHeaderPointerDown,
    onHeaderClick,
}: PanelProps): ReactElement {
    const hoverSfx = useHoverSfx('panel');

    function handleMouseDown(_e: MouseEvent<HTMLDivElement>): void {
        if (onFocus) onFocus();
    }

    return (
        <div
            className={cn('lib-panel', focused && 'focused', className)}
            style={style}
            onMouseDown={handleMouseDown}
            onMouseEnter={hoverSfx}
        >
            {/* Corner brackets */}
            <span className="lib-panel__ck tl" />
            <span className="lib-panel__ck tr" />
            <span className="lib-panel__ck bl" />
            <span className="lib-panel__ck br" />

            {/* Side rails */}
            <span className="lib-panel__rail l" />
            <span className="lib-panel__rail r" />

            {/* Circumnavigating trace */}
            <span className="lib-panel__trace">
                <i className="l" />
                <i className="r" />
            </span>

            {/* Header */}
            <div
                className="lib-panel__hdr"
                ref={headerRef}
                onPointerDown={onHeaderPointerDown}
                onClick={onHeaderClick}
            >
                {ix !== undefined && <span className="ix">{ix}</span>}
                <span className="tt">{title}</span>
                <span className="dots">
                    <i />
                    <i />
                    <i />
                </span>
                {actions !== undefined && <span className="lib-panel__hdr-actions">{actions}</span>}
                {badge !== undefined && <span className="badge">{badge}</span>}
            </div>

            {/* Body */}
            <div className="lib-panel__body">{children}</div>
        </div>
    );
}

export default Panel;
