import { useCallback, useEffect, useRef, useState } from 'react';
import type { ReactElement } from 'react';
import { usePanelAvailable } from '@app/providers/PanelAvailabilityProvider';
import { useNowPlaying } from '../../hooks/useNowPlaying';
import { useSpotifyPlayer } from '../../hooks/useSpotifyPlayer';
import { sendSpotifyCmd } from '../../nowplayingApi';
import { payloadToTrack, sdkStateToTrack } from '../../utils';
import { AVAILABILITY_TIMEOUT_MS, JARVIS_DEVICE_NAME } from '../../constants';
import { AuthPrompt } from '../AuthPrompt';
import { SpotifyFullPanel } from '../SpotifyFullPanel';
import { NowPlayingCompact } from '../NowPlayingCompact';
import { PlayerErrorState } from '../PlayerErrorState';
import { PremiumRequiredState } from '../PremiumRequiredState';
import { NoPlaybackState } from './NoPlaybackState';
import type { SpotifyCmdAction } from '../../types';
import type { NowPlayingPanelProps } from './NowPlayingPanel.types';

export function NowPlayingPanel({ mode = 'expanded' }: NowPlayingPanelProps): ReactElement | null {
    const { payload, hasLiveData } = useNowPlaying();
    const sdkPlayer = useSpotifyPlayer();
    const [backendAvailable, setBackendAvailable] = useState(true);
    const availabilityTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    usePanelAvailable('nowplaying', backendAvailable || payload !== null);

    useEffect(() => {
        availabilityTimerRef.current = setTimeout(() => {
            setBackendAvailable(false);
        }, AVAILABILITY_TIMEOUT_MS);

        return () => {
            if (availabilityTimerRef.current) clearTimeout(availabilityTimerRef.current);
        };
    }, []);

    useEffect(() => {
        if (hasLiveData && availabilityTimerRef.current) {
            clearTimeout(availabilityTimerRef.current);
            availabilityTimerRef.current = null;
            setBackendAvailable(true);
        }
    }, [hasLiveData, payload]);

    // True when JARVIS is the active Spotify Connect device.
    const jarvisIsActive =
        sdkPlayer.isReady &&
        payload?.device === JARVIS_DEVICE_NAME;

    // When JARVIS is the active device, use the lower-latency SDK state.
    // Otherwise fall back to the polled WS payload.
    const effectiveTrack =
        jarvisIsActive && sdkPlayer.sdkPlayerState !== null
            ? sdkStateToTrack(sdkPlayer.sdkPlayerState, payload?.device ?? JARVIS_DEVICE_NAME)
            : payload !== null
              ? payloadToTrack(payload)
              : null;

    const sendCmd = useCallback(
        (action: SpotifyCmdAction, value?: number): void => {
            if (jarvisIsActive) {
                if (action === 'play' || action === 'pause') {
                    sdkPlayer.togglePlay().catch((err: unknown) => {
                        console.warn('[JARVIS] SDK togglePlay failed:', err);
                    });
                    return;
                }
                if (action === 'next') {
                    // NOTE: If the user has switched the active device (e.g. to their phone) via
                    // the Spotify Connect picker, nextTrack() fires on the SDK but produces no
                    // audible change because the phone is the active device. The user must switch
                    // back to JARVIS via the Spotify app. We do not attempt to fix this here.
                    sdkPlayer.nextTrack().catch((err: unknown) => {
                        console.warn('[JARVIS] SDK nextTrack failed:', err);
                    });
                    return;
                }
                if (action === 'prev') {
                    sdkPlayer.previousTrack().catch((err: unknown) => {
                        console.warn('[JARVIS] SDK previousTrack failed:', err);
                    });
                    return;
                }
                if (action === 'seek' && value !== undefined) {
                    sdkPlayer.seek(value).catch((err: unknown) => {
                        console.warn('[JARVIS] SDK seek failed:', err);
                    });
                    return;
                }
                if (action === 'volume' && value !== undefined) {
                    // Spotify SDK expects 0..1; transport sends 0..100.
                    sdkPlayer.setVolume(value / 100).catch((err: unknown) => {
                        console.warn('[JARVIS] SDK setVolume failed:', err);
                    });
                    return;
                }
            }
            // Non-SDK path: the WS handler may not support 'seek' today — that's OK, the SDK path
            // is the priority. For non-SDK devices, this is a best-effort forward.
            sendSpotifyCmd(action, value);
        },
        [jarvisIsActive, sdkPlayer],
    );

    // Backend not available — hide the panel.
    if (!backendAvailable && !hasLiveData) return null;

    // Show live data when available.
    if (payload !== null) {
        if (!payload.authenticated) {
            return <AuthPrompt scopeUpgrade={payload.scope_upgrade_required} />;
        }

        // SDK account_error → premium gate (replaces the full panel).
        // This is the single source of truth for the Premium gate: only the SDK
        // account_error event sets premiumRequired, not play-mutation 402 responses
        // (which can be per-resource restrictions, not user-level Premium status).
        if (sdkPlayer.error?.kind === 'account_error') {
            return <PremiumRequiredState />;
        }

        if (!effectiveTrack) {
            if (mode === 'compact') {
                return <NoPlaybackState />;
            }
            return (
                <>
                    {sdkPlayer.error !== null && <PlayerErrorState error={sdkPlayer.error} />}
                    <SpotifyFullPanel track={null} onCmd={sendCmd} />
                </>
            );
        }

        const fullPanel = (
            <>
                {sdkPlayer.error !== null && <PlayerErrorState error={sdkPlayer.error} />}
                <SpotifyFullPanel track={effectiveTrack} onCmd={sendCmd} />
            </>
        );

        return mode === 'compact' ? (
            <NowPlayingCompact track={effectiveTrack} onCmd={sendCmd} />
        ) : (
            fullPanel
        );
    }

    // Waiting for first frame — show empty state.
    return <NoPlaybackState />;
}

export default NowPlayingPanel;
