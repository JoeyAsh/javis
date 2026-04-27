import { useEffect, useRef, useCallback } from 'react';
import { useAppDispatch, useAppSelector } from '@app';
import {
    setSdkDeviceId,
    setSdkReady,
    setSdkError,
    setPremiumRequired,
    setSdkPlayerState,
} from '../nowplayingSlice';
import {
    selectSdkDeviceId,
    selectSdkIsReady,
    selectSdkError,
    selectSdkPlayerState,
} from '../nowplayingSelectors';
import { useGetSpotifyTokenQuery } from '../nowplayingApi';
import { sendSpotifyDeviceAnnounce } from '../nowplayingApi';
import { loadSpotifySdk, createPlayer } from '../spotifySdk';
import type { SpotifyPlayerHandle, SpotifySdkError } from '../spotifySdk';
import { JARVIS_DEVICE_NAME, SDK_INITIAL_VOLUME } from '../constants';
import { playerHandleRegistry } from '../spotifyPlayerHandleRegistry';
import type { UseSpotifyPlayerReturn } from './useSpotifyPlayer.types';

function toSdkError(err: unknown): SpotifySdkError {
    if (
        typeof err === 'object' &&
        err !== null &&
        'kind' in err &&
        'message' in err
    ) {
        const cast = err as { kind: unknown; message: unknown };
        const kind = cast.kind;
        if (
            kind === 'initialization_error' ||
            kind === 'authentication_error' ||
            kind === 'account_error' ||
            kind === 'playback_error'
        ) {
            return { kind, message: String(cast.message) };
        }
    }
    return { kind: 'initialization_error', message: String(err) };
}

export function useSpotifyPlayer(): UseSpotifyPlayerReturn {
    const dispatch = useAppDispatch();

    const deviceId = useAppSelector(selectSdkDeviceId);
    const isReady = useAppSelector(selectSdkIsReady);
    const error = useAppSelector(selectSdkError);
    const sdkPlayerState = useAppSelector(selectSdkPlayerState);

    // RTK Query token — auto-refreshes per keepUnusedDataFor TTL.
    const { data: tokenData } = useGetSpotifyTokenQuery();

    // Stable ref for the latest token — the SDK getOAuthToken callback reads
    // from here so it always delivers a fresh token without re-creating the player.
    const tokenRef = useRef<string | null>(null);
    // Keep dispatch stable via ref so effect closures don't go stale.
    const dispatchRef = useRef(dispatch);
    dispatchRef.current = dispatch;

    // Track whether we've already started the init flow.
    const initializedRef = useRef(false);
    const playerHandleRef = useRef<SpotifyPlayerHandle | null>(null);

    // Update tokenRef whenever RTK Query refreshes the token.
    useEffect(() => {
        if (tokenData !== undefined) {
            tokenRef.current = tokenData.accessToken;
        }
    }, [tokenData]);

    // Stable getter — reads from ref so the player never needs re-creating on refresh.
    const getToken = useCallback((): Promise<string> => {
        const token = tokenRef.current;
        if (token !== null) return Promise.resolve(token);
        return Promise.reject(new Error('No Spotify token available'));
    }, []);

    // One-time initialisation — runs when the first token arrives.
    // Guarded by `initializedRef` so token refreshes don't tear down the player.
    useEffect(() => {
        if (tokenData === undefined) return;
        if (initializedRef.current) return;
        initializedRef.current = true;

        // Ensure the ref is primed before the async path begins.
        tokenRef.current = tokenData.accessToken;

        let cancelled = false;

        async function init(): Promise<void> {
            try {
                await loadSpotifySdk();
                if (cancelled) return;

                const handle = await createPlayer({
                    name: JARVIS_DEVICE_NAME,
                    getToken,
                    volume: SDK_INITIAL_VOLUME,
                });

                if (cancelled) {
                    handle.disconnect();
                    return;
                }

                playerHandleRef.current = handle;
                playerHandleRegistry.set(handle);
                dispatchRef.current(setSdkDeviceId(handle.deviceId));
                dispatchRef.current(setSdkReady(true));
                sendSpotifyDeviceAnnounce(handle.deviceId, JARVIS_DEVICE_NAME, true);

                handle.onStateChange((state) => {
                    if (!cancelled) dispatchRef.current(setSdkPlayerState(state));
                });

                handle.onError((sdkErr) => {
                    if (cancelled) return;
                    dispatchRef.current(setSdkError(sdkErr));
                    if (sdkErr.kind === 'account_error') {
                        dispatchRef.current(setPremiumRequired(true));
                    }
                    if (
                        sdkErr.kind === 'playback_error' &&
                        sdkErr.message === 'Device went offline'
                    ) {
                        dispatchRef.current(setSdkReady(false));
                        dispatchRef.current(setSdkDeviceId(null));
                        sendSpotifyDeviceAnnounce(null, JARVIS_DEVICE_NAME, false);
                    }
                });
            } catch (err: unknown) {
                if (cancelled) return;
                const sdkErr = toSdkError(err);
                dispatchRef.current(setSdkError(sdkErr));
                if (sdkErr.kind === 'account_error') {
                    dispatchRef.current(setPremiumRequired(true));
                }
            }
        }

        void init();

        return () => {
            cancelled = true;
            playerHandleRef.current?.disconnect();
            playerHandleRef.current = null;
            playerHandleRegistry.set(null);
            dispatchRef.current(setSdkReady(false));
            dispatchRef.current(setSdkDeviceId(null));
            sendSpotifyDeviceAnnounce(null, JARVIS_DEVICE_NAME, false);
        };
    // initializedRef and tokenRef are plain refs — not reactive.
    // getToken is stable (no deps). The only actual reactive dep is tokenData.
    }, [tokenData, getToken]);

    const setVolume = useCallback((value: number): Promise<void> => {
        return playerHandleRef.current?.setVolume(value) ?? Promise.resolve();
    }, []);

    const togglePlay = useCallback((): Promise<void> => {
        return playerHandleRef.current?.togglePlay() ?? Promise.resolve();
    }, []);

    const nextTrack = useCallback((): Promise<void> => {
        return playerHandleRef.current?.nextTrack() ?? Promise.resolve();
    }, []);

    const previousTrack = useCallback((): Promise<void> => {
        return playerHandleRef.current?.previousTrack() ?? Promise.resolve();
    }, []);

    const seek = useCallback((positionMs: number): Promise<void> => {
        return playerHandleRef.current?.seek(positionMs) ?? Promise.resolve();
    }, []);

    return {
        deviceId,
        isReady,
        error,
        sdkPlayerState,
        setVolume,
        togglePlay,
        nextTrack,
        previousTrack,
        seek,
    };
}
