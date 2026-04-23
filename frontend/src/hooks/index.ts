export { useWebSocket, subscribeSystemMetrics, subscribeSpotifyStateStream } from './useWebSocket';
export type { SpotifyStateListener } from './useWebSocket';
export { useAudioAnalyser } from './useAudioAnalyser';
// useSystemMetrics removed — consume via @features/system useSystem() hook
// useConversationMode removed — consume via @features/conversation
// usePushToTalk removed — consume via @features/conversation
// useMicStream removed — consume via @features/conversation
// useSettings moved to @features/settings — re-exported here for backward compat
export { useSettings } from '../features/settings/hooks/useSettings';
export type { JarvisSettings, UseSettingsReturn } from '../features/settings/hooks/useSettings.types';
export type { OrbStyle } from '../features/settings/types';
export { useLocation } from './useLocation';
export type { LocationCoords } from './useLocation';
