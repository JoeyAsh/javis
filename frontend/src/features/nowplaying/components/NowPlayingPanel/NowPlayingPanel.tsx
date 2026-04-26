import { useCallback, useEffect, useRef, useState } from 'react';
import type { ReactElement } from 'react';
import { usePanelAvailable } from '@app/providers/PanelAvailabilityProvider';
import { useNowPlaying } from '../../hooks/useNowPlaying';
import { sendSpotifyCmd } from '../../nowplayingApi';
import { payloadToTrack } from '../../utils';
import { AVAILABILITY_TIMEOUT_MS } from '../../constants';
import { AuthPrompt } from '../AuthPrompt';
import { SpotifyFullPanel } from '../SpotifyFullPanel';
import { NowPlayingCompact } from '../NowPlayingCompact';
import { NoPlaybackState } from './NoPlaybackState';
import type { SpotifyCmdAction } from '../../types';
import type { NowPlayingPanelProps } from './NowPlayingPanel.types';

export function NowPlayingPanel({ mode = 'expanded' }: NowPlayingPanelProps): ReactElement | null {
    const { payload, hasLiveData } = useNowPlaying();
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

    const sendCmd = useCallback((action: SpotifyCmdAction, value?: number): void => {
        sendSpotifyCmd(action, value);
    }, []);

    // Backend not available — hide the panel.
    if (!backendAvailable && !hasLiveData) return null;

    // Show live data when available.
    if (payload !== null) {
        if (!payload.authenticated) {
            return <AuthPrompt scopeUpgrade={payload.scope_upgrade_required} />;
        }
        const liveTrack = payloadToTrack(payload);
        if (!liveTrack) {
            if (mode === 'compact') {
                return <NoPlaybackState />;
            }
            return <SpotifyFullPanel track={null} onCmd={sendCmd} />;
        }
        return mode === 'compact' ? (
            <NowPlayingCompact track={liveTrack} onCmd={sendCmd} />
        ) : (
            <SpotifyFullPanel track={liveTrack} onCmd={sendCmd} />
        );
    }

    // Waiting for first frame — show empty state.
    return <NoPlaybackState />;
}

export default NowPlayingPanel;
