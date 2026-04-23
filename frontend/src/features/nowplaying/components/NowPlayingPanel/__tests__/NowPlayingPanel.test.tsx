/**
 * NowPlayingPanel — Vitest + RTL tests.
 *
 * Dispatches spotifyStateReceived directly (bypassing RTK Query async
 * onCacheEntryAdded) for deterministic, fast tests.
 * Outgoing commands are asserted via vi.spyOn(wsClient, 'send').
 */
import { act, fireEvent, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { installMockWsClient } from '@test/mockWsClient';
import { renderWithProviders } from '@test/renderWithProviders';
import nowplayingReducer, { spotifyStateReceived } from '../../../nowplayingSlice';
import { NowPlayingPanel } from '../NowPlayingPanel';
import type { SpotifyStatePayload } from '../../../types';
import { wsClient } from '@core/websocket/wsClient';

const ws = installMockWsClient();

const livePayload: SpotifyStatePayload = {
    authenticated: true,
    track: {
        name: 'Midnight City',
        artist: 'M83',
        album: "Hurry Up, We're Dreaming",
        albumArtUrl: undefined,
        durationMs: 241_000,
        progressMs: 113_000,
        isPlaying: true,
    },
    device: {
        name: 'Studio Monitors',
        type: 'Speaker',
        volumePercent: 72,
    },
};

const unauthPayload: SpotifyStatePayload = {
    authenticated: false,
};

const noTrackPayload: SpotifyStatePayload = {
    authenticated: true,
    track: undefined,
    device: undefined,
};

beforeEach(() => {
    ws.reset();
    vi.useFakeTimers();
});

afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
});

describe('NowPlayingPanel — live spotify_state track info', () => {
    it('renders track title, artist and album from live payload', () => {
        const { store } = renderWithProviders(<NowPlayingPanel mode="expanded" />, {
            reducers: { nowplaying: nowplayingReducer },
        });

        act(() => {
            store.dispatch(spotifyStateReceived(livePayload));
        });

        expect(screen.getByText('Midnight City')).toBeInTheDocument();
        expect(screen.getAllByText('M83').length).toBeGreaterThanOrEqual(1);
        expect(screen.getByText("Hurry Up, We're Dreaming")).toBeInTheDocument();
    });

    it('renders pause button when track is playing', () => {
        const { store } = renderWithProviders(<NowPlayingPanel mode="expanded" />, {
            reducers: { nowplaying: nowplayingReducer },
        });

        act(() => {
            store.dispatch(spotifyStateReceived(livePayload));
        });

        expect(screen.getByRole('button', { name: /pause/i })).toBeInTheDocument();
    });

    it('shows NO ACTIVE PLAYBACK before live data arrives', () => {
        renderWithProviders(<NowPlayingPanel mode="expanded" />, {
            reducers: { nowplaying: nowplayingReducer },
        });
        expect(screen.getByText(/NO ACTIVE PLAYBACK/i)).toBeInTheDocument();
    });
});

describe('NowPlayingPanel — transport button commands', () => {
    it('play/pause toggle sends pause cmd when playing', () => {
        const sendSpy = vi.spyOn(wsClient, 'send');

        const { store } = renderWithProviders(<NowPlayingPanel mode="expanded" />, {
            reducers: { nowplaying: nowplayingReducer },
        });

        act(() => {
            store.dispatch(spotifyStateReceived(livePayload));
        });

        const pauseBtn = screen.getByRole('button', { name: /pause/i });
        fireEvent.click(pauseBtn);

        expect(sendSpy).toHaveBeenCalledWith(
            expect.objectContaining({
                type: 'spotify_cmd',
                payload: expect.objectContaining({ action: 'pause' }),
            }),
        );
    });

    it('previous button sends prev cmd', () => {
        const sendSpy = vi.spyOn(wsClient, 'send');

        const { store } = renderWithProviders(<NowPlayingPanel mode="expanded" />, {
            reducers: { nowplaying: nowplayingReducer },
        });

        act(() => {
            store.dispatch(spotifyStateReceived(livePayload));
        });

        fireEvent.click(screen.getByRole('button', { name: /previous/i }));
        expect(sendSpy).toHaveBeenCalledWith(
            expect.objectContaining({
                type: 'spotify_cmd',
                payload: expect.objectContaining({ action: 'prev' }),
            }),
        );
    });
});

describe('NowPlayingPanel — unauthenticated state', () => {
    it('renders VERBINDEN button when authenticated is false', () => {
        const { store } = renderWithProviders(<NowPlayingPanel mode="expanded" />, {
            reducers: { nowplaying: nowplayingReducer },
        });

        act(() => {
            store.dispatch(spotifyStateReceived(unauthPayload));
        });

        expect(screen.getByRole('button', { name: /log in to spotify/i })).toBeInTheDocument();
        expect(screen.getByText('VERBINDEN')).toBeInTheDocument();
    });

    it('VERBINDEN button opens auth URL in new tab', () => {
        const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null);

        const { store } = renderWithProviders(<NowPlayingPanel mode="expanded" />, {
            reducers: { nowplaying: nowplayingReducer },
        });

        act(() => {
            store.dispatch(spotifyStateReceived(unauthPayload));
        });

        fireEvent.click(screen.getByRole('button', { name: /log in to spotify/i }));
        expect(openSpy).toHaveBeenCalledWith(
            'http://127.0.0.1:8766/oauth/spotify/start',
            '_blank',
            'noopener,noreferrer',
        );

        openSpy.mockRestore();
    });
});

describe('NowPlayingPanel — no active playback', () => {
    it('does not crash when authenticated payload has no track', () => {
        expect(() => {
            const { store } = renderWithProviders(<NowPlayingPanel />, {
                reducers: { nowplaying: nowplayingReducer },
            });
            act(() => {
                store.dispatch(spotifyStateReceived(noTrackPayload));
            });
        }).not.toThrow();
    });

    it('shows NO ACTIVE PLAYBACK when authenticated but no track', () => {
        const { store } = renderWithProviders(<NowPlayingPanel mode="expanded" />, {
            reducers: { nowplaying: nowplayingReducer },
        });

        act(() => {
            store.dispatch(spotifyStateReceived(noTrackPayload));
        });

        expect(screen.getByText(/NO ACTIVE PLAYBACK/i)).toBeInTheDocument();
    });
});

describe('NowPlayingPanel — compact mode', () => {
    it('renders track title in compact mode', () => {
        const { store } = renderWithProviders(<NowPlayingPanel mode="compact" />, {
            reducers: { nowplaying: nowplayingReducer },
        });

        act(() => {
            store.dispatch(spotifyStateReceived(livePayload));
        });

        expect(screen.getByText('Midnight City')).toBeInTheDocument();
    });
});
