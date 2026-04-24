import {
    useCallback,
    useRef,
    type ReactElement,
    type MouseEvent,
    type PointerEvent as ReactPointerEvent,
} from 'react';
import { Panel } from '../../primitives/Panel/Panel';
import { useDraggable } from '../hooks/useDraggable';
import type { DragState } from '../hooks/useDraggable';
import { useResizable } from '../hooks/useResizable';
import type { ResizeDir, ResizeState } from '../hooks/useResizable';
import { useClickSfx, useHoverSfx } from '@core/audio';
import { useSfx } from '@core/audio';
import type { WindowProps, WindowState } from './Window.types';

const DOUBLE_CLICK_MS = 300;

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
    mode = 'compact',
    onFocus,
    onDragStart,
    onDragMove,
    onDragEnd,
    onResizeStart,
    onResizeMove,
    onResizeEnd,
    onReset,
    onClose,
    onModeToggle,
    draggable = true,
    resizable = true,
    className,
    itemRenderer,
}: WindowProps): ReactElement {
    const { playOneShot } = useSfx();
    const hoverButtonSfx = useHoverSfx('button');

    const handleFocus = useCallback((): void => {
        if (onFocus) onFocus(id);
    }, [id, onFocus]);

    const handleDragStart = useCallback(
        (e: PointerEvent): void => {
            if (onDragStart) {
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

    const handleResizeStartCb = useCallback(
        (dir: ResizeDir, e: PointerEvent): void => {
            if (onResizeStart) onResizeStart(id, dir, e as unknown as ReactPointerEvent);
        },
        [id, onResizeStart],
    );

    const handleResizeMoveCb = useCallback(
        (resizeState: ResizeState, e: PointerEvent): void => {
            if (onResizeMove && resizeState.dir !== null) {
                onResizeMove(id, resizeState.dir, resizeState.dx, resizeState.dy, e);
            }
        },
        [id, onResizeMove],
    );

    const handleResizeEndCb = useCallback(
        (_resizeState: ResizeState, e: PointerEvent): void => {
            if (onResizeEnd) onResizeEnd(id, e);
        },
        [id, onResizeEnd],
    );

    const { onPointerDown: handleResizePointerDown, resizing } = useResizable({
        onStart: handleResizeStartCb,
        onMove: handleResizeMoveCb,
        onEnd: handleResizeEndCb,
        disabled: !resizable,
    });

    const handlePointerDownCapture = useCallback((): void => {
        if (onFocus) onFocus(id);
    }, [id, onFocus]);

    const handleReset = useCallback(
        (e: MouseEvent<HTMLButtonElement>): void => {
            e.stopPropagation();
            playOneShot('click');
            playOneShot('recall');
            if (onReset) onReset(id);
        },
        [id, onReset, playOneShot],
    );

    const handleClose = useCallback(
        (e: MouseEvent<HTMLButtonElement>): void => {
            e.stopPropagation();
            if (onClose) onClose(id);
        },
        [id, onClose],
    );

    const handleModeToggle = useCallback(
        (e: MouseEvent<HTMLButtonElement>): void => {
            e.stopPropagation();
            playOneShot('click');
            playOneShot(mode === 'compact' ? 'expand' : 'collapse');
            if (onModeToggle) onModeToggle(id);
        },
        [id, mode, onModeToggle, playOneShot],
    );

    const onCloseClick = useClickSfx(handleClose);

    const lastClickRef = useRef(0);
    const handleHeaderClick = useCallback(
        (e: MouseEvent<HTMLDivElement>): void => {
            const target = e.target as HTMLElement | null;
            if (target && target.closest('[data-no-drag]')) return;
            const now = performance.now();
            if (now - lastClickRef.current < DOUBLE_CLICK_MS) {
                if (onModeToggle) onModeToggle(id);
                lastClickRef.current = 0;
            } else {
                lastClickRef.current = now;
            }
        },
        [id, onModeToggle],
    );

    const effectiveState: WindowState = resizing ? 'resizing' : dragging ? 'dragging' : state;

    const rootStyle = {
        left: position.x,
        top: position.y,
        width: position.w,
        height: position.h,
    };

    const rootCls = ['lib-window', className].filter(Boolean).join(' ');

    const headerLeft = (
        <span className="lib-window__hdr-drag" data-testid="window-drag-handle">
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

    const hasModeToggle = onModeToggle !== undefined;
    const hasActions = onReset !== undefined || hasModeToggle || onClose !== undefined;

    const headerActions = hasActions ? (
        <>
            {onReset !== undefined && (
                <button
                    className="lib-window__btn"
                    aria-label="Reset window"
                    title="Reset"
                    onClick={handleReset}
                    onMouseEnter={hoverButtonSfx}
                    onPointerDown={(e) => e.stopPropagation()}
                    type="button"
                    data-no-drag
                    data-sfx-hover="button"
                >
                    <RotateCcwIcon />
                </button>
            )}
            {hasModeToggle && (
                <button
                    className="lib-window__btn"
                    aria-label={mode === 'compact' ? 'Undock window' : 'Dock window'}
                    title={mode === 'compact' ? 'Undock' : 'Dock'}
                    onClick={handleModeToggle}
                    onMouseEnter={hoverButtonSfx}
                    onPointerDown={(e) => e.stopPropagation()}
                    type="button"
                    data-no-drag
                    data-sfx-hover="button"
                >
                    {mode === 'compact' ? <SquareIcon /> : <Minimize2Icon />}
                </button>
            )}
            {onClose !== undefined && (
                <button
                    className="lib-window__btn lib-window__btn--close"
                    aria-label="Close window"
                    title="Close"
                    onClick={onCloseClick}
                    onMouseEnter={hoverButtonSfx}
                    onPointerDown={(e) => e.stopPropagation()}
                    type="button"
                    data-no-drag
                    data-sfx-hover="button"
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
            data-mode={mode}
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
                onHeaderPointerDown={handlePointerDown}
                onHeaderClick={handleHeaderClick}
                style={{ height: '100%', display: 'flex', flexDirection: 'column' }}
            >
                <div className="lib-window__body">
                    {itemRenderer({ mode, focused, dragging: dragging || resizing })}
                </div>
            </Panel>
            {resizable && (
                <>
                    <span
                        className="lib-window__resize lib-window__resize--n"
                        onPointerDown={handleResizePointerDown('n')}
                        data-testid="resize-n"
                    />
                    <span
                        className="lib-window__resize lib-window__resize--s"
                        onPointerDown={handleResizePointerDown('s')}
                        data-testid="resize-s"
                    />
                    <span
                        className="lib-window__resize lib-window__resize--e"
                        onPointerDown={handleResizePointerDown('e')}
                        data-testid="resize-e"
                    />
                    <span
                        className="lib-window__resize lib-window__resize--w"
                        onPointerDown={handleResizePointerDown('w')}
                        data-testid="resize-w"
                    />
                    <span
                        className="lib-window__resize lib-window__resize--ne"
                        onPointerDown={handleResizePointerDown('ne')}
                        data-testid="resize-ne"
                    />
                    <span
                        className="lib-window__resize lib-window__resize--nw"
                        onPointerDown={handleResizePointerDown('nw')}
                        data-testid="resize-nw"
                    />
                    <span
                        className="lib-window__resize lib-window__resize--se"
                        onPointerDown={handleResizePointerDown('se')}
                        data-testid="resize-se"
                    />
                    <span
                        className="lib-window__resize lib-window__resize--sw"
                        onPointerDown={handleResizePointerDown('sw')}
                        data-testid="resize-sw"
                    />
                </>
            )}
        </div>
    );
}

export default Window;
