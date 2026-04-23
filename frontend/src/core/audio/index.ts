export { AudioEngine, getAudioEngine, __resetAudioEngineSingleton } from './audioEngine';
export { SfxContext, SfxProvider, useSfx } from './SfxContext';
export type { SfxContextValue, SfxProviderProps } from './SfxContext';
export { useClickSfx, useHoverSfx } from './hooks';
export type { HoverSfxTarget, UseHoverSfxOptions } from './hooks';
export { useAudioEngine } from './useAudioEngine';
export type { UseAudioEngineReturn } from './useAudioEngine';
export { useTauriWindowSfx } from './useTauriWindowSfx';
export { useAudioAnalyser } from './useAudioAnalyser';
// useMicStream moved to @features/conversation — import from there.
export type { SfxEvent, SfxEntry } from './config';
export { SFX_CONFIG, DUCK_VOLUME, DUCK_RAMP_MS } from './config';
export { audioPlaybackSlice, audioEnqueued, audioConsumed, playingChanged, bargeInRequested } from './audioPlaybackSlice';
export type { AudioChannel, AudioPlaybackState } from './audioPlaybackSlice';
export { audioPlaybackApi, useStreamAudioPlaybackQuery } from './audioPlaybackApi';
export { useAudioPlayback } from './useAudioPlayback';
export type { UseAudioPlaybackReturn } from './useAudioPlayback.types';
