/**
 * useTauriWindowSfx — listens to Tauri window maximize/minimize events and
 * fires SFX accordingly.
 * Copy of src/lib/audio/useTauriWindowSfx.ts — original remains in place.
 * Imports adjusted for new location within core/audio/.
 */

import { useEffect } from 'react';
import type { TauriWindowSfxProps } from './useTauriWindowSfx.types';

export function useTauriWindowSfx({ playOneShot }: TauriWindowSfxProps): void {
    useEffect(() => {
        if (typeof window === 'undefined' || !('__TAURI__' in window)) {
            return;
        }

        let mounted = true;
        let unlisten: (() => void) | null = null;

        async function register(): Promise<void> {
            try {
                const tauriWindow = await (
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
