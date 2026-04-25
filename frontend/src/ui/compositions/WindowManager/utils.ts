import type { SlotRect } from '../../window/slotGrid';
import type { ResizeDir } from '../../window/hooks/useResizable';
import type { ExpandedRect, ViewportSize } from './WindowManager.types';
import { MIN_EXPANDED_W, MIN_EXPANDED_H } from './constants';
import { TOP_BAR_HEIGHT } from '../../window/slotGrid';

export function getViewport(): ViewportSize {
    return {
        w: typeof window !== 'undefined' ? window.innerWidth : 1280,
        h: typeof window !== 'undefined' ? window.innerHeight : 900,
    };
}

/**
 * Compute a new SlotRect after a resize gesture.
 */
export function applyResize(
    start: SlotRect,
    dir: ResizeDir,
    dx: number,
    dy: number,
    minW = 120,
    minH = 80,
): SlotRect {
    let { x, y, w, h } = start;

    if (dir.includes('e')) {
        w = Math.max(minW, start.w + dx);
    }
    if (dir.includes('s')) {
        h = Math.max(minH, start.h + dy);
    }
    if (dir.includes('w')) {
        const newW = Math.max(minW, start.w - dx);
        x = start.x + (start.w - newW);
        w = newW;
    }
    if (dir.includes('n')) {
        const newH = Math.max(minH, start.h - dy);
        y = start.y + (start.h - newH);
        h = newH;
    }

    return { x, y, w, h };
}

/** Clamp an expanded rect so it stays within the visible workspace. */
export function clampExpandedRect(rect: ExpandedRect, W: number, H: number): ExpandedRect {
    const w = Math.max(MIN_EXPANDED_W, Math.min(rect.w, W));
    const h = Math.max(MIN_EXPANDED_H, Math.min(rect.h, H - TOP_BAR_HEIGHT));
    const x = Math.max(0, Math.min(rect.x, Math.max(0, W - w)));
    const y = Math.max(TOP_BAR_HEIGHT, Math.min(rect.y, Math.max(TOP_BAR_HEIGHT, H - h)));
    return { x, y, w, h };
}

/**
 * Derive a sensible default floating rect when a window is first expanded.
 * Centers approximately on the slot at ~1.8× width / 1.6× height.
 */
export function defaultExpandedRect(slotRect: SlotRect, W: number, H: number): ExpandedRect {
    const cx = slotRect.x + slotRect.w / 2;
    const cy = slotRect.y + slotRect.h / 2;
    const w = Math.floor(slotRect.w * 1.8);
    const h = Math.floor(slotRect.h * 1.6);
    const x = Math.floor(cx - w / 2);
    const y = Math.floor(cy - h / 2);
    return clampExpandedRect({ x, y, w, h }, W, H);
}
