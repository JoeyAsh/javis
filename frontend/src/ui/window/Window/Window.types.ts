import type { ReactNode, PointerEvent as ReactPointerEvent } from 'react';
import type { ResizeDir } from '../hooks/useResizable';

export type PanelMode = 'compact' | 'expanded';

export interface PanelContentRenderProps {
    mode: PanelMode;
    focused: boolean;
    dragging: boolean;
}

export type WindowState =
    | 'idle'
    | 'dragging'
    | 'snap-preview'
    | 'swap-preview'
    | 'settling'
    | 'focused'
    | 'resizing';

export interface WindowProps {
    id: string;
    title?: ReactNode;
    ix?: ReactNode;
    badge?: ReactNode;
    position: { x: number; y: number; w: number; h: number };
    state?: WindowState;
    focused?: boolean;
    mode?: PanelMode;
    onFocus?: (id: string) => void;
    onDragStart?: (id: string, e: ReactPointerEvent) => void;
    onDragMove?: (id: string, dx: number, dy: number, e: PointerEvent) => void;
    onDragEnd?: (id: string, e: PointerEvent) => void;
    onResizeStart?: (id: string, dir: ResizeDir, e: ReactPointerEvent) => void;
    onResizeMove?: (id: string, dir: ResizeDir, dx: number, dy: number, e: PointerEvent) => void;
    onResizeEnd?: (id: string, e: PointerEvent) => void;
    onReset?: (id: string) => void;
    onClose?: (id: string) => void;
    onModeToggle?: (id: string) => void;
    draggable?: boolean;
    resizable?: boolean;
    className?: string;
    itemRenderer: (props: PanelContentRenderProps) => ReactNode;
}
