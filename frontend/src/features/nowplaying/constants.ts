export const SPOTIFY_AUTH_URL = 'http://127.0.0.1:8766/oauth/spotify/start';
export const AVAILABILITY_TIMEOUT_MS = 10_000;
export const WAVE_BARS = 7;
export const SEARCH_DEBOUNCE_MS = 400;
export const LIBRARY_PAGE_LIMIT = 50;
export const JARVIS_DEVICE_NAME = 'JARVIS';
export const SDK_INITIAL_VOLUME = 0.5;
/** Initial UI volume level (0..100 scale matching TransportControls slider). */
export const INITIAL_UI_VOLUME = 50;
/**
 * "Prev" button restart threshold (ms). Matches Spotify mobile/desktop UX:
 * - If current position > threshold → restart the current song (seek to 0).
 * - Otherwise → go to the previous track.
 */
export const PREV_RESTART_THRESHOLD_MS = 3_000;
