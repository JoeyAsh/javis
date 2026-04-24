/**
 * SfxContext — React context that exposes `playOneShot`, `play`, and `stop`.
 * Copy of src/lib/audio/SfxContext.tsx — original remains in place.
 * Imports adjusted for new location within core/audio/.
 */

import { createContext, useContext } from 'react';
import type { ReactElement } from 'react';
import type { SfxContextValue, SfxProviderProps } from './SfxContext.types';

/** Fallback: no-ops so components don't crash outside a provider in tests. */
const defaultValue: SfxContextValue = {
    playOneShot: () => undefined,
    play: () => undefined,
    stop: () => undefined,
};

export const SfxContext = createContext<SfxContextValue>(defaultValue);

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

export type { SfxContextValue, SfxProviderProps };

export default SfxContext;
