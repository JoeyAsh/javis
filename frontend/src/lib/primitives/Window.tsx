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
    /** Restore the window to its original position/slot. */
    onReset?: (id: string) => void;
    /** If not provided the close button is omitted. */
    onClose?: (id: string) => void;
    /** Default true. */
    draggable?: boolean;
    className?: string;
    children?: ReactNode;
}

/** RotateCcw icon at 11 px — reset/restore to home slot. */
function RotateCcwIcon(): ReactElement {
    return (
        <svg
            width="11"
            height="11"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden
            focusable="false"
        >
            <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
            <path d="M3 3v5h5" />
        </svg>
    );
}

/** Minus icon at 11 px — minimize. */
function MinusIcon(): ReactElement {
    return (
        <svg
            width="11"
            height="11"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden
            focusable="false"
        >
            <line x1="5" y1="12" x2="19" y2="12" />
        </svg>
    );
}

/** Square icon at 11 px — maximize. */
function SquareIcon(): ReactElement {
    return (
        <svg
            width="11"
            height="11"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden
            focusable="false"
        >
            <rect x="4" y="4" width="16" height="16" />
        </svg>
    );
}

/** Minimize2 icon at 11 px — restore from maximized. */
function Minimize2Icon(): ReactElement {
    return (
        <svg
            width="11"
            height="11"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden
            focusable="false"
        >
            <polyline points="4 14 10 14 10 20" />
            <polyline points="20 10 14 10 14 4" />
            <line x1="10" y1="14" x2="3" y2="21" />
            <line x1="21" y1="3" x2="14" y2="10" />
        </svg>
    );
}

/** X icon at 11 px — close. */
function XIcon(): ReactElement {
    return (
        <svg
            width="11"
            height="11"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.75"
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
    onReset,
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

    const handleReset = useCallback(
        (e: React.MouseEvent<HTMLButtonElement>): void => {
            e.stopPropagation();
            if (onReset) onReset(id);
        },
        [id, onReset],
    );

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

    // Header action cluster — order: Reset · Minimize · Maximize · Close.
    const hasActions =
        onReset !== undefined ||
        onMinimize !== undefined ||
        onMaximize !== undefined ||
        onClose !== undefined;

    const headerActions = hasActions ? (
        <>
            {onReset !== undefined && (
                <button
                    className="lib-window__btn"
                    aria-label="Reset window"
                    title="Reset"
                    onClick={handleReset}
                    type="button"
                >
                    <RotateCcwIcon />
                </button>
            )}
            {onMinimize !== undefined && (
                <button
                    className="lib-window__btn"
                    aria-label="Minimize window"
                    title="Minimize"
                    onClick={handleMinimize}
                    type="button"
                >
                    <MinusIcon />
                </button>
            )}
            {onMaximize !== undefined && (
                <button
                    className="lib-window__btn"
                    aria-label={
                        effectiveState === 'maximized' ? 'Restore window' : 'Maximize window'
                    }
                    title={effectiveState === 'maximized' ? 'Restore' : 'Maximize'}
                    onClick={handleMaximize}
                    type="button"
                >
                    {effectiveState === 'maximized' ? <Minimize2Icon /> : <SquareIcon />}
                </button>
            )}
            {onClose !== undefined && (
                <button
                    className="lib-window__btn lib-window__btn--close"
                    aria-label="Close window"
                    title="Close"
                    onClick={handleClose}
                    type="button"
                >
                    <XIcon />
                </button>
            )}
        </>
    ) : undefined;

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
                badge={badge}
                actions={headerActions}
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
