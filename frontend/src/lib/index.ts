/**
 * @deprecated — import from '@ui' instead.
 *
 * This shim re-exports everything from the canonical '@ui' barrel so existing
 * imports from '../lib' or '@/lib' continue to resolve without modification.
 * It will be removed once all consumers have been migrated.
 */
export * from '@ui';

// CssOrb as the legacy 'Orb' name for backward-compat
export { CssOrb as Orb } from '@ui';
export type { CssOrbProps as OrbProps } from '@ui';

// Audio — re-export from @core/audio
export { SfxProvider, useSfx, SfxContext } from '@core/audio';
export type { SfxContextValue, SfxProviderProps } from '@core/audio';
export { useAudioEngine } from '@core/audio';
export type { UseAudioEngineReturn } from '@core/audio';
export { useTauriWindowSfx } from '@core/audio';
export { AudioEngine } from '@core/audio';
export { SFX_CONFIG, DUCK_VOLUME, DUCK_RAMP_MS } from '@core/audio';
export type { SfxEvent, SfxEntry } from '@core/audio';
export { useClickSfx, useHoverSfx } from '@core/audio';
export type { HoverSfxTarget, UseHoverSfxOptions } from '@core/audio';
