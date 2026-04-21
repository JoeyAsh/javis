/**
 * SfxContext — React context that exposes `playOneShot`, `play`, and `stop`
 * to any component in the tree without prop-drilling or direct engine imports.
 *
 * Usage:
 *   // In a provider ancestor (App.tsx wraps with <SfxProvider>):
 *   <SfxProvider playOneShot={...} play={...} stop={...}>…</SfxProvider>
 *
 *   // In any descendant:
 *   const { playOneShot, play, stop } = useSfx();
 *   playOneShot('click');
 *   play('drag_move');
 *   stop('drag_move');
 */

import { createContext, useContext } from 'react';
import type { ReactElement, ReactNode } from 'react';
import type { SfxEvent } from './config';

export interface SfxContextValue {
    playOneShot: (event: SfxEvent) => void;
    play: (event: SfxEvent) => void;
    stop: (event: SfxEvent) => void;
}

/** Fallback: no-ops so components don't crash outside a provider in tests. */
const defaultValue: SfxContextValue = {
    playOneShot: () => undefined,
    play: () => undefined,
    stop: () => undefined,
};

export const SfxContext = createContext<SfxContextValue>(defaultValue);

export interface SfxProviderProps {
    playOneShot: (event: SfxEvent) => void;
    play: (event: SfxEvent) => void;
    stop: (event: SfxEvent) => void;
    children: ReactNode;
}

/**
 * Wraps the subtree with the SFX playback functions derived from
 * `useAudioEngine`. Mount once at the App root.
 */
export function SfxProvider({
    playOneShot,
    play,
    stop,
    children,
}: SfxProviderProps): ReactElement {
    const value: SfxContextValue = { playOneShot, play, stop };
    return <SfxContext.Provider value={value}>{children}</SfxContext.Provider>;
}

/**
 * Consume the SFX context. Falls back to no-ops if used outside a provider
 * (convenient in unit tests that don't care about SFX).
 */
export function useSfx(): SfxContextValue {
    return useContext(SfxContext);
}

export default SfxContext;
