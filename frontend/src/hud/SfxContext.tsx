/**
 * SfxContext — React context that exposes `playOneShot` to any component
 * in the tree without prop-drilling or direct engine imports.
 *
 * Usage:
 *   // In a provider ancestor (App.tsx wraps with <SfxProvider>):
 *   <SfxProvider playOneShot={engine.playOneShot}>…</SfxProvider>
 *
 *   // In any descendant:
 *   const { playOneShot } = useSfx();
 *   playOneShot('click');
 */

import { createContext, useContext } from 'react';
import type { ReactElement, ReactNode } from 'react';
import type { SfxEvent } from '../config/audio';

export interface SfxContextValue {
  playOneShot: (event: SfxEvent) => void;
}

/** Fallback: no-op so components don't crash outside a provider in tests. */
const defaultValue: SfxContextValue = {
  playOneShot: () => undefined,
};

export const SfxContext = createContext<SfxContextValue>(defaultValue);

export interface SfxProviderProps {
  playOneShot: (event: SfxEvent) => void;
  children: ReactNode;
}

/**
 * Wraps the subtree with the SFX playback function derived from
 * `useAudioEngine`. Mount once at the App root.
 */
export function SfxProvider({ playOneShot, children }: SfxProviderProps): ReactElement {
  const value: SfxContextValue = { playOneShot };
  return <SfxContext.Provider value={value}>{children}</SfxContext.Provider>;
}

/**
 * Consume the SFX context. Falls back to a no-op if used outside a provider
 * (convenient in unit tests that don't care about SFX).
 */
export function useSfx(): SfxContextValue {
  return useContext(SfxContext);
}

export default SfxContext;
