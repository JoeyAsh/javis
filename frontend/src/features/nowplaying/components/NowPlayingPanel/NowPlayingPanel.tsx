import { useCallback, useEffect, useRef, useState } from 'react';
import type { ReactElement } from 'react';
import { usePanelAvailable } from '@app/providers/PanelAvailabilityProvider';
import { useMockTicker } from '@common/hooks/useMockTicker';
import { useNowPlaying } from '../../hooks/useNowPlaying';
import { sendSpotifyCmd } from '../../nowplayingApi';
import { payloadToTrack } from '../../utils';
import { AVAILABILITY_TIMEOUT_MS } from '../../constants';
import { AuthPrompt } from '../AuthPrompt';
import { TrackInfo } from '../TrackInfo';
import { TransportControls } from '../TransportControls';
import { ProgressBar } from '../ProgressBar';
import type { SpotifyCmdAction } from '../../types';
import type { NowPlayingPanelProps, NowPlayingCompactProps, NowPlayingExpandedProps } from './NowPlayingPanel.types';
import styles from './NowPlayingPanel.module.css';

// ---------------------------------------------------------------------------
// No-playback state
// ---------------------------------------------------------------------------

function NoPlaybackState(): ReactElement {
    return (
        <div className={styles.state}>
            <span className={styles.stateLabel}>NO ACTIVE PLAYBACK</span>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Compact view
// ---------------------------------------------------------------------------

function NowPlayingCompact({ track, onCmd }: NowPlayingCompactProps): ReactElement {
    const tick = useMockTicker(1000, !track.playing);
    const progress = track.playing
        ? (track.progressMs + tick * 1000) % track.durationMs
        : track.progressMs;
    const pct = Math.min(100, (progress / track.durationMs) * 100);

    return (
        <div className={styles.compact}>
            <div className={styles.compactTitle}>{track.title}</div>
            <div className={styles.compactArtist}>{track.artist}</div>
            <div className={styles.compactRow}>
                <div className={styles.compactBar}>
                    <div className={styles.compactBarFill} style={{ width: `${pct}%` }} />
                </div>
                <button
                    type="button"
                    aria-label={track.playing ? 'Pause' : 'Play'}
                    data-no-drag
                    className={styles.compactPlayBtn}
                    onClick={() => onCmd(track.playing ? 'pause' : 'play')}
                >
                    {track.playing ? '⏸' : '▶'}
                </button>
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Expanded view
// ---------------------------------------------------------------------------

function NowPlayingExpanded({ track, onCmd }: NowPlayingExpandedProps): ReactElement {
    return (
        <div className={styles.panel}>
            <TrackInfo track={track} />
            <ProgressBar track={track} />
            <TransportControls track={track} onCmd={onCmd} />
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

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
            return <AuthPrompt />;
        }
        const liveTrack = payloadToTrack(payload);
        if (!liveTrack) {
            return <NoPlaybackState />;
        }
        return mode === 'compact' ? (
            <NowPlayingCompact track={liveTrack} onCmd={sendCmd} />
        ) : (
            <NowPlayingExpanded track={liveTrack} onCmd={sendCmd} />
        );
    }

    // Waiting for first frame — show empty state or mock.
    return <NoPlaybackState />;
}

export default NowPlayingPanel;
