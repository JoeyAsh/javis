import type { ReactNode } from 'react';
import type { SlotId } from '../../window/slotGrid';
import type { PanelMode, PanelContentRenderProps } from '../../window/Window';

export type { PanelMode, PanelContentRenderProps };

export interface ManagedWindow {
    id: string;
    title?: ReactNode;
    ix?: ReactNode;
    badge?: ReactNode;
    /**
     * Render-prop content. Receives the current mode, focused state, and
     * dragging state so the consumer can render compact vs expanded views.
     */
    itemRenderer: (props: PanelContentRenderProps) => ReactNode;
}

/** Rectangular geometry used for the expanded (free-floating) position. */
export interface ExpandedRect {
    x: number;
    y: number;
    w: number;
    h: number;
}

export interface WindowManagerProps {
    /** Windows to render. */
    windows: ManagedWindow[];
    /** windowId → slotId (controlled). */
    assignments: Record<string, SlotId>;
    /** Called when assignments should change (drop → move or swap). */
    onAssignmentsChange: (next: Record<string, SlotId>) => void;
    /**
     * Original "home" slot assignments used by Reset. Defaults to the value of
     * `assignments` on first render if not provided.
     */
    homeAssignments?: Record<string, SlotId>;
    /** Focused window id (controlled). */
    focusedId?: string | null;
    /** Called when a window is focused / blur (null = no focus). */
    onFocusChange?: (id: string | null) => void;

    // ── Mode — controlled/uncontrolled ────────────────────────────────────────

    /**
     * Controlled mode map. When provided, WindowManager uses these values
     * instead of its internal mode state.
     */
    modes?: Record<string, PanelMode>;
    /**
     * Called when a window's mode should change.
     */
    onModesChange?: (next: Record<string, PanelMode>) => void;

    /**
     * Controlled expanded-rect map.
     */
    expandedRects?: Record<string, ExpandedRect>;

    className?: string;
}
