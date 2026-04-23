/**
 * Shared SFX helper hooks for interactive lib components.
 * Copy of src/lib/audio/hooks.ts — original remains in place.
 */

import { useCallback, useRef } from 'react';
import type { MouseEvent } from 'react';
import { useSfx } from './SfxContext';

export type HoverSfxTarget = 'button' | 'panel';

export interface UseHoverSfxOptions {
    throttleMs?: number;
}

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
