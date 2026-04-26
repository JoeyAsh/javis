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
        payload?.device?.name === JARVIS_DEVICE_NAME;

    // When JARVIS is the active device, use the lower-latency SDK state.
    // Otherwise fall back to the polled WS payload.
    const effectiveTrack =
        jarvisIsActive && sdkPlayer.sdkPlayerState !== null
            ? sdkStateToTrack(sdkPlayer.sdkPlayerState, payload?.device?.name ?? JARVIS_DEVICE_NAME)
            : payload !== null
              ? payloadToTrack(payload)
              : null;

    const sendCmd = useCallback(
        (action: SpotifyCmdAction, value?: number): void => {
            if (jarvisIsActive) {
                if (action === 'play' || action === 'pause') {
                    sdkPlayer.togglePlay();
                    return;
                }
                if (action === 'next') {
                    sdkPlayer.nextTrack();
                    return;
                }
                if (action === 'prev') {
                    sdkPlayer.previousTrack();
                    return;
                }
                if (action === 'volume' && value !== undefined) {
                    // Spotify SDK expects 0..1; transport sends 0..100.
                    sdkPlayer.setVolume(value / 100);
                    return;
                }
            }
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
