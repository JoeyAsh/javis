/**
 * SfxContext — React context that exposes `playOneShot`, `play`, and `stop`.
 * Copy of src/lib/audio/SfxContext.tsx — original remains in place.
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

export function SfxProvider({
    playOneShot,
    play,
    stop,
    children,
}: SfxProviderProps): ReactElement {
    const value: SfxContextValue = { playOneShot, play, stop };
    return <SfxContext.Provider value={value}>{children}</SfxContext.Provider>;
}

export function useSfx(): SfxContextValue {
    return useContext(SfxContext);
}

export default SfxContext;
