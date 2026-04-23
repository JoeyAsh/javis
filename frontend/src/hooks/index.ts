export { useWebSocket, subscribeSystemMetrics, subscribeSpotifyStateStream } from './useWebSocket';
export type { SpotifyStateListener } from './useWebSocket';
export { useAudioAnalyser } from './useAudioAnalyser';
// useSystemMetrics removed — consume via @features/system useSystem() hook
// useConversationMode removed — consume via @features/conversation
// usePushToTalk removed — consume via @features/conversation
// useMicStream removed — consume via @features/conversation
export { useSettings } from './useSettings';
export type { JarvisSettings, UseSettingsReturn } from './useSettings';
export { useLocation } from './useLocation';
export type { LocationCoords } from './useLocation';
