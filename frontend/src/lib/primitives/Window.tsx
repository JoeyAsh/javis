import {
    useCallback,
    type ReactElement,
    type ReactNode,
    type PointerEvent as ReactPointerEvent,
} from 'react';
import { Panel } from './Panel';
import { useDraggable } from '../hooks/useDraggable';
import type { DragState } from '../hooks/useDraggable';
import './Window.css';

export type WindowState =
    | 'idle'
    | 'dragging'
    | 'snap-preview'
    | 'swap-preview'
    | 'settling'
    | 'focused'
    | 'minimized'
    | 'maximized';

export interface WindowProps {
    /** Stable window id passed back to all callbacks. */
    id: string;
    title?: ReactNode;
    ix?: ReactNode;
    badge?: ReactNode;
    /** Absolute position + size. Parent (WindowManager) owns this. */
    position: { x: number; y: number; w: number; h: number };
    /** Visual state — purely driven from outside. */
    state?: WindowState;
    focused?: boolean;
    onFocus?: (id: string) => void;
    onDragStart?: (id: string, e: ReactPointerEvent) => void;
    onDragMove?: (id: string, dx: number, dy: number, e: PointerEvent) => void;
    onDragEnd?: (id: string, e: PointerEvent) => void;
    onMinimize?: (id: string) => void;
    onMaximize?: (id: string) => void;
    /** If not provided the close button is omitted. */
    onClose?: (id: string) => void;
    /** Default true. */
    draggable?: boolean;
    className?: string;
    children?: ReactNode;
}

/** Minus icon at 12 px — minimize. */
function MinusIcon(): ReactElement {
    return (
        <svg
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden
            focusable="false"
        >
            <line x1="5" y1="12" x2="19" y2="12" />
        </svg>
    );
}

/** Square icon at 12 px — maximize. */
function SquareIcon(): ReactElement {
    return (
        <svg
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden
            focusable="false"
        >
            <rect x="4" y="4" width="16" height="16" />
        </svg>
    );
}

/** X icon at 12 px — close. */
function XIcon(): ReactElement {
    return (
        <svg
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden
            focusable="false"
        >
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
    );
}

export function Window({
    id,
    title,
    ix,
    badge,
    position,
    state = 'idle',
    focused = false,
    onFocus,
    onDragStart,
    onDragMove,
    onDragEnd,
    onMinimize,
    onMaximize,
    onClose,
    draggable = true,
    className,
    children,
}: WindowProps): ReactElement {
    const handleFocus = useCallback((): void => {
        if (onFocus) onFocus(id);
    }, [id, onFocus]);

    const handleDragStart = useCallback(
        (e: PointerEvent): void => {
            if (onDragStart) {
                // We can't create a real ReactPointerEvent from a native one, so
                // we cast for the callback signature contract.
                onDragStart(id, e as unknown as ReactPointerEvent);
            }
        },
        [id, onDragStart],
    );

    const handleDragMove = useCallback(
        (dragState: DragState, e: PointerEvent): void => {
            if (onDragMove) onDragMove(id, dragState.dx, dragState.dy, e);
        },
        [id, onDragMove],
    );

    const handleDragEnd = useCallback(
        (_dragState: DragState, e: PointerEvent): void => {
            if (onDragEnd) onDragEnd(id, e);
        },
        [id, onDragEnd],
    );

    const { onPointerDown: handlePointerDown, dragging } = useDraggable({
        onStart: handleDragStart,
        onMove: handleDragMove,
        onEnd: handleDragEnd,
        disabled: !draggable,
    });

    const handlePointerDownCapture = useCallback((): void => {
        if (onFocus) onFocus(id);
    }, [id, onFocus]);

    const handleMinimize = useCallback(
        (e: React.MouseEvent<HTMLButtonElement>): void => {
            e.stopPropagation();
            if (onMinimize) onMinimize(id);
        },
        [id, onMinimize],
    );

    const handleMaximize = useCallback(
        (e: React.MouseEvent<HTMLButtonElement>): void => {
            e.stopPropagation();
            if (onMaximize) onMaximize(id);
        },
        [id, onMaximize],
    );

    const handleClose = useCallback(
        (e: React.MouseEvent<HTMLButtonElement>): void => {
            e.stopPropagation();
            if (onClose) onClose(id);
        },
        [id, onClose],
    );

    // Resolve the effective visual state: if we're actively dragging, override.
    const effectiveState: WindowState = dragging ? 'dragging' : state;

    const rootStyle =
        effectiveState === 'maximized'
            ? undefined // CSS handles fixed inset:16px
            : {
                  left: position.x,
                  top: position.y,
                  width: position.w,
                  height: position.h,
              };

    const rootCls = ['lib-window', className].filter(Boolean).join(' ');

    // Header left (drag area): ix + title
    const headerLeft = (
        <span
            className="lib-window__hdr-drag"
            onPointerDown={handlePointerDown}
            data-testid="window-drag-handle"
        >
            {ix !== undefined && (
                <span style={{ color: 'var(--accent-bright)', fontWeight: 500, opacity: 0.8 }}>
                    {ix}
                </span>
            )}
            <span
                style={{
                    flex: 1,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                }}
            >
                {title}
            </span>
        </span>
    );

    // Header right: action buttons.
    const headerRight = (
        <span className="lib-window__hdr-actions" data-no-drag>
            {onMinimize !== undefined && (
                <button
                    className="lib-window__hdr-btn"
                    aria-label="Minimize window"
                    onClick={handleMinimize}
                    type="button"
                >
                    <MinusIcon />
                </button>
            )}
            {onMaximize !== undefined && (
                <button
                    className="lib-window__hdr-btn"
                    aria-label="Maximize window"
                    onClick={handleMaximize}
                    type="button"
                >
                    <SquareIcon />
                </button>
            )}
            {onClose !== undefined && (
                <button
                    className="lib-window__hdr-btn lib-window__hdr-btn--close"
                    aria-label="Close window"
                    onClick={handleClose}
                    type="button"
                >
                    <XIcon />
                </button>
            )}
        </span>
    );

    // The Panel's badge slot is repurposed to hold the header actions when any
    // action callback is provided; otherwise badge flows through normally.
    const panelBadge =
        onMinimize !== undefined || onMaximize !== undefined || onClose !== undefined
            ? headerRight
            : badge;

    return (
        <div
            className={rootCls}
            data-state={effectiveState}
            data-window-id={id}
            style={rootStyle}
            role="dialog"
            aria-label={typeof title === 'string' ? title : undefined}
            onPointerDownCapture={handlePointerDownCapture}
        >
            <Panel
                ix={headerLeft}
                title={undefined}
                badge={panelBadge}
                focused={focused}
                onFocus={handleFocus}
                style={{ height: '100%', display: 'flex', flexDirection: 'column' }}
            >
                <div className="lib-window__body">{children}</div>
            </Panel>
        </div>
    );
}

export default Window;
