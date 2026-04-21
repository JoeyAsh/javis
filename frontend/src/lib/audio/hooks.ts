/**
 * Shared SFX helper hooks for interactive lib components.
 *
 * useClickSfx — wraps an onClick handler to play `click` before invoking it.
 * useHoverSfx — plays `hover_button` or `hover_panel` on mouseenter with
 *               throttling and panel-suppression when a button is the source.
 */

import { useCallback, useRef } from 'react';
import type { MouseEvent } from 'react';
import { useSfx } from './SfxContext';

export type HoverSfxTarget = 'button' | 'panel';

export interface UseHoverSfxOptions {
    throttleMs?: number;
}

/**
 * Returns an onClick handler that plays `click` then invokes the optional
 * wrapped handler. Safe to use when handler is undefined.
 */
export function useClickSfx<E extends { currentTarget: unknown }>(
    handler?: (e: E) => void,
): (e: E) => void {
    const { playOneShot } = useSfx();
    return useCallback(
        (e: E) => {
            playOneShot('click');
            handler?.(e);
        },
        [handler, playOneShot],
    );
}

/**
 * Returns an onMouseEnter handler that plays `hover_button` or `hover_panel`.
 *
 * Panel variant is suppressed when the pointer entered via a button
 * (target.closest('[data-sfx-hover="button"]') matches).
 * Throttled per-instance (default 150 ms) to prevent rapid re-triggers.
 */
export function useHoverSfx(
    target: HoverSfxTarget,
    options: UseHoverSfxOptions = {},
): (e: MouseEvent) => void {
    const { throttleMs = 150 } = options;
    const { playOneShot } = useSfx();
    const lastRef = useRef(0);
    return useCallback(
        (e: MouseEvent) => {
            if (target === 'panel') {
                const el = e.target as Element | null;
                if (el && el.closest('[data-sfx-hover="button"]')) return;
            }
            const now = performance.now();
            if (now - lastRef.current < throttleMs) return;
            lastRef.current = now;
            playOneShot(target === 'button' ? 'hover_button' : 'hover_panel');
        },
        [target, throttleMs, playOneShot],
    );
}
