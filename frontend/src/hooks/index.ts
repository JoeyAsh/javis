/**
 * @deprecated Legacy hooks barrel — consumers should import from their
 * canonical locations directly.
 *
 * Shims kept for backward compatibility:
 *   useAudioAnalyser → @core/audio
 *   useSettings → @features/settings
 *   useLocation → @common/hooks/useLocation
 *
 * useWebSocket is no longer re-exported here.
 * Its functionality has been migrated to:
 *   - @core/audio (audioPlaybackApi, useAudioPlayback)
 *   - @features/orbState (orbStateApi)
 *   - @core/websocket/commands (sendTranscript, sendCancelTurn)
 */

export { useAudioAnalyser } from './useAudioAnalyser';
// useSettings moved to @features/settings — re-exported here for backward compat
export { useSettings } from '../features/settings/hooks/useSettings';
export type { JarvisSettings, UseSettingsReturn } from '../features/settings/hooks/useSettings.types';
export type { OrbStyle } from '../features/settings/types';
export { useLocation } from './useLocation';
export type { LocationCoords } from '@common/types/location';
