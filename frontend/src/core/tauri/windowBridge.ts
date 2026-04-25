/**
 * windowBridge — Tauri-specific window event utilities.
 *
 * Currently a thin namespace stub. The actual window event logic lives in
 * core/audio/useTauriWindowSfx.ts. This module will grow to include
 * window state helpers (maximize, minimize, fullscreen) as needed.
 *
 * Safe to import in browser environments — all exports degrade silently
 * when the Tauri runtime is absent.
 */

/** Returns true when the Tauri runtime is present in the current environment. */
export function isTauriEnvironment(): boolean {
    return typeof window !== 'undefined' && '__TAURI__' in window;
}

// TODO: Extract window event registration from useTauriWindowSfx into a
// standalone registerWindowEvents(callbacks) function here.
