/**
 * useTauriWindowSfx — listens to Tauri window maximize/minimize events and
 * fires SFX accordingly.
 *
 * - maximize → `transition_1`
 * - minimize → `transition_2`
 *
 * The Tauri API is accessed via a runtime check on `window.__TAURI__` so this
 * hook is a silent no-op in browser/dev mode where the Tauri runtime is absent.
 * No throws, no console errors in browser mode — purely optional enhancement.
 *
 * Implementation note: we avoid importing `@tauri-apps/api/window` at module
 * scope because it does not exist at type-check time in non-Tauri builds.
 * Instead we check for the Tauri global and use the WS event listener API via
 * the Tauri global if present.
 */

import { useEffect } from 'react';
import type { SfxEvent } from '../config/audio';

interface TauriWindowSfxProps {
    playOneShot: (event: SfxEvent) => void;
}

/**
 * Registers Tauri window event listeners on mount and cleans them up on unmount.
 * Safe to call in all environments — degrades silently if Tauri is unavailable.
 */
export function useTauriWindowSfx({ playOneShot }: TauriWindowSfxProps): void {
    useEffect(() => {
        // Guard: only proceed if the Tauri runtime is present.
        if (typeof window === 'undefined' || !('__TAURI__' in window)) {
            return;
        }

        let mounted = true;
        let unlisten: (() => void) | null = null;

        async function register(): Promise<void> {
            try {
                // Dynamic import via string to avoid static analysis of the module path.
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                const tauriWindow: any = await (
                    Function('specifier', 'return import(specifier)') as (
                        s: string,
                    ) => Promise<unknown>
                )('@tauri-apps/api/window');
                if (!mounted) return;

                const appWindow = (
                    tauriWindow as {
                        getCurrentWindow: () => {
                            listen: (event: string, cb: () => void) => Promise<() => void>;
                            isMaximized: () => Promise<boolean>;
                        };
                    }
                ).getCurrentWindow();

                const unlistenFn = await appWindow.listen('tauri://resize', () => {
                    void appWindow.isMaximized().then((maximized: boolean) => {
                        if (!mounted) return;
                        playOneShot(maximized ? 'transition_1' : 'transition_2');
                    });
                });

                if (!mounted) {
                    unlistenFn();
                    return;
                }
                unlisten = unlistenFn;
            } catch {
                // Tauri API unavailable (browser mode) — silent no-op.
            }
        }

        void register();

        return () => {
            mounted = false;
            unlisten?.();
        };
    }, [playOneShot]);
}

export default useTauriWindowSfx;
