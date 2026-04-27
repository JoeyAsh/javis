/// <reference path="./spotifySdk.d.ts" />
/**
 * Spotify Web Playback SDK adapter.
 *
 * Responsibilities:
 * - Lazy-load the SDK script exactly once (idempotent).
 * - Wrap `new window.Spotify.Player(...)` with a typed, event-driven handle.
 *
 * Window augmentation for `window.Spotify` lives in the sibling spotifySdk.d.ts.
 *
 * This module is NOT a React component and NOT a hook.
 * Consumers call loadSpotifySdk() then createPlayer(...).
 */

export type SpotifySdkError =
    | { kind: 'initialization_error'; message: string }
    | { kind: 'authentication_error'; message: string }
    | { kind: 'account_error'; message: string }
    | { kind: 'playback_error'; message: string };

export interface SpotifySdkPlayerState {
    isPaused: boolean;
    positionMs: number;
    durationMs: number;
    track: { uri: string; name: string; artist: string; album: string } | null;
    shuffle: boolean;
    repeat: 'off' | 'context' | 'track';
}

export interface SpotifyPlayerHandle {
    deviceId: string;
    setVolume: (value: number) => Promise<void>;
    getVolume: () => number;
    duck: (factor: number, rampMs: number) => Promise<void>;
    restore: (rampMs: number) => Promise<void>;
    togglePlay: () => Promise<void>;
    nextTrack: () => Promise<void>;
    previousTrack: () => Promise<void>;
    seek: (positionMs: number) => Promise<void>;
    disconnect: () => void;
    onStateChange: (cb: (state: SpotifySdkPlayerState) => void) => () => void;
    onError: (cb: (err: SpotifySdkError) => void) => () => void;
}

// ---------------------------------------------------------------------------
// Internal SDK script loader — idempotent promise
// ---------------------------------------------------------------------------

let sdkReadyPromise: Promise<void> | null = null;

export function loadSpotifySdk(): Promise<void> {
    if (sdkReadyPromise !== null) {
        return sdkReadyPromise;
    }

    sdkReadyPromise = new Promise<void>((resolve) => {
        // SDK fires window.onSpotifyWebPlaybackSDKReady when loaded.
        window.onSpotifyWebPlaybackSDKReady = () => {
            resolve();
        };

        // Inject the script tag if not already present.
        const existing = document.querySelector<HTMLScriptElement>(
            'script[src="https://sdk.scdn.co/spotify-player.js"]',
        );
        if (existing === null) {
            const script = document.createElement('script');
            script.src = 'https://sdk.scdn.co/spotify-player.js';
            script.async = true;
            document.body.appendChild(script);
        }
    });

    return sdkReadyPromise;
}

// ---------------------------------------------------------------------------
// Repeat-mode mapper
// ---------------------------------------------------------------------------

function mapRepeatMode(mode: 0 | 1 | 2): 'off' | 'context' | 'track' {
    if (mode === 1) return 'context';
    if (mode === 2) return 'track';
    return 'off';
}

// ---------------------------------------------------------------------------
// Player factory
// ---------------------------------------------------------------------------

export function createPlayer(args: {
    name: string;
    getToken: () => Promise<string>;
    volume: number;
}): Promise<SpotifyPlayerHandle> {
    return new Promise<SpotifyPlayerHandle>((resolve, reject) => {
        const stateListeners = new Set<(state: SpotifySdkPlayerState) => void>();
        const errorListeners = new Set<(err: SpotifySdkError) => void>();

        const emitError = (err: SpotifySdkError): void => {
            errorListeners.forEach((cb) => cb(err));
        };

        const player = new window.Spotify.Player({
            name: args.name,
            getOAuthToken: (cb: (token: string) => void) => {
                args.getToken().then(cb).catch(() => cb(''));
            },
            volume: args.volume,
        });

        let resolved = false;

        // ---------------------------------------------------------------------------
        // Volume tracking + cosine-ramp duck/restore helpers
        // ---------------------------------------------------------------------------

        /** Last volume value we set on the SDK (0..1). */
        let _lastVolume = args.volume;
        /** Volume captured before the first duck; null means not currently ducked. */
        let _preDuckVolume: number | null = null;
        /** Active ramp animation frame handle — cancel before starting a new ramp. */
        let _rampRafId: number | null = null;

        /**
         * Animate `player.setVolume()` from `from` to `to` over `rampMs` using a
         * cosine ease. Cancels any in-progress ramp first.
         */
        function cosineRamp(from: number, to: number, rampMs: number): Promise<void> {
            if (_rampRafId !== null) {
                cancelAnimationFrame(_rampRafId);
                _rampRafId = null;
            }

            if (rampMs <= 0 || from === to) {
                _lastVolume = to;
                return player.setVolume(to);
            }

            return new Promise<void>((rampResolve) => {
                const startTime = performance.now();

                function tick(): void {
                    const elapsed = performance.now() - startTime;
                    const progress = Math.min(elapsed / rampMs, 1);
                    // Cosine ease: 0 → 1, smooth start and end.
                    const eased = (1 - Math.cos(progress * Math.PI)) / 2;
                    const current = from + (to - from) * eased;

                    _lastVolume = current;
                    void player.setVolume(current);

                    if (progress < 1) {
                        _rampRafId = requestAnimationFrame(tick);
                    } else {
                        _rampRafId = null;
                        rampResolve();
                    }
                }

                _rampRafId = requestAnimationFrame(tick);
            });
        }

        player.addListener('ready', (event: SpotifyReadyEvent) => {
            if (resolved) return;
            resolved = true;

            const handle: SpotifyPlayerHandle = {
                deviceId: event.device_id,

                setVolume: (value) => {
                    _lastVolume = value;
                    return player.setVolume(value);
                },

                getVolume: () => _lastVolume,

                duck: async (factor, rampMs) => {
                    // Idempotent: if already ducked, no-op.
                    if (_preDuckVolume !== null) return;
                    _preDuckVolume = _lastVolume;
                    const target = _preDuckVolume * factor;
                    await cosineRamp(_lastVolume, target, rampMs);
                },

                restore: async (rampMs) => {
                    if (_preDuckVolume === null) return;
                    const target = _preDuckVolume;
                    _preDuckVolume = null;
                    await cosineRamp(_lastVolume, target, rampMs);
                },

                togglePlay: () => player.togglePlay(),
                nextTrack: () => player.nextTrack(),
                previousTrack: () => player.previousTrack(),
                seek: (positionMs) => player.seek(positionMs),
                disconnect: () => {
                    if (_rampRafId !== null) {
                        cancelAnimationFrame(_rampRafId);
                        _rampRafId = null;
                    }
                    player.disconnect();
                },
                onStateChange: (cb) => {
                    stateListeners.add(cb);
                    return () => { stateListeners.delete(cb); };
                },
                onError: (cb) => {
                    errorListeners.add(cb);
                    return () => { errorListeners.delete(cb); };
                },
            };

            resolve(handle);
        });

        player.addListener('not_ready', (_event: SpotifyReadyEvent) => {
            // Caller's onError subscription will handle "not_ready" as a lifecycle event,
            // but we don't reject here — the handle is still valid.
            emitError({ kind: 'playback_error', message: 'Device went offline' });
        });

        player.addListener('player_state_changed', (state: SpotifyPlaybackState | null) => {
            if (state === null) return;

            const currentTrack = state.track_window.current_track;
            const mapped: SpotifySdkPlayerState = {
                isPaused: state.paused,
                positionMs: state.position,
                durationMs: state.duration,
                track: {
                    uri: currentTrack.uri,
                    name: currentTrack.name,
                    artist: currentTrack.artists[0]?.name ?? '',
                    album: currentTrack.album.name,
                },
                shuffle: state.shuffle,
                repeat: mapRepeatMode(state.repeat_mode),
            };

            stateListeners.forEach((cb) => cb(mapped));
        });

        player.addListener('initialization_error', (event: SpotifyPlayerErrorEvent) => {
            const err: SpotifySdkError = { kind: 'initialization_error', message: event.message };
            if (!resolved) {
                resolved = true;
                reject(err);
            } else {
                emitError(err);
            }
        });

        player.addListener('authentication_error', (event: SpotifyPlayerErrorEvent) => {
            const err: SpotifySdkError = { kind: 'authentication_error', message: event.message };
            if (!resolved) {
                resolved = true;
                reject(err);
            } else {
                emitError(err);
            }
        });

        player.addListener('account_error', (event: SpotifyPlayerErrorEvent) => {
            const err: SpotifySdkError = { kind: 'account_error', message: event.message };
            if (!resolved) {
                resolved = true;
                reject(err);
            } else {
                emitError(err);
            }
        });

        player.addListener('playback_error', (event: SpotifyPlayerErrorEvent) => {
            emitError({ kind: 'playback_error', message: event.message });
        });

        player.connect().catch((connectErr: unknown) => {
            if (!resolved) {
                resolved = true;
                reject({
                    kind: 'initialization_error',
                    message: connectErr instanceof Error ? connectErr.message : 'SDK connect() failed',
                } satisfies SpotifySdkError);
            }
        });
    });
}
