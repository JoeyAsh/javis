/**
 * NowPlayingPanel — Vitest + RTL tests.
 *
 * All WS subscriptions and sends are intercepted via vi.mock so no real
 * network connection is attempted. Tests cover:
 *   - Renders track info from live spotify_state payload
 *   - Play/pause toggle dispatches correct spotify_cmd
 *   - Volume slider dispatches volume cmd after debounce
 *   - Unauthenticated state renders VERBINDEN connect button
 *   - No crash when track payload is absent (no active playback)
 */
import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// ---------------------------------------------------------------------------
// Mock the WS subscription + send helpers
// ---------------------------------------------------------------------------

import type { SpotifyStateListener } from '../../../hooks/useWebSocket';

let capturedSpotifyListener: SpotifyStateListener | null = null;

// vi.mock is hoisted — use vi.hoisted() to create the spy before the factory runs.
const mockSendFn = vi.hoisted(() => vi.fn());

vi.mock('../../../hooks/useWebSocket', () => ({
  subscribeSpotifyStateStream: vi.fn((listener: SpotifyStateListener) => {
    capturedSpotifyListener = listener;
    return () => {
      capturedSpotifyListener = null;
    };
  }),
  sendSpotifyCmdStream: mockSendFn,
}));

// Import after mocking
import { NowPlayingPanel } from '../NowPlaying';
import type { SpotifyStatePayload } from '../../../types';

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

const livePayload: SpotifyStatePayload = {
  authenticated: true,
  track: {
    name: 'Midnight City',
    artist: 'M83',
    album: 'Hurry Up, We\'re Dreaming',
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

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderPanel(mode: 'compact' | 'expanded' = 'expanded') {
  return render(<NowPlayingPanel mode={mode} />);
}

// ---------------------------------------------------------------------------
// Test suites
// ---------------------------------------------------------------------------

describe('NowPlayingPanel — live spotify_state track info', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    capturedSpotifyListener = null;
    mockSendFn.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it('renders track title, artist and album from live payload', () => {
    renderPanel();

    act(() => {
      capturedSpotifyListener?.(livePayload);
    });

    expect(screen.getByText('Midnight City')).toBeInTheDocument();
    // M83 appears both as monogram and artist — use getAllByText
    expect(screen.getAllByText('M83').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Hurry Up, We\'re Dreaming')).toBeInTheDocument();
  });

  it('renders play/pause button matching isPlaying state', () => {
    renderPanel();

    act(() => {
      capturedSpotifyListener?.(livePayload);
    });

    // track.isPlaying = true → button label should be "Pause"
    expect(screen.getByRole('button', { name: /pause/i })).toBeInTheDocument();
  });

  it('falls back to NO ACTIVE PLAYBACK before grace period and no live data', () => {
    renderPanel();

    // No live payload, still within grace window
    expect(screen.getByText(/NO ACTIVE PLAYBACK/i)).toBeInTheDocument();
  });

  it('shows mock data after 2s grace period with no live payload', () => {
    renderPanel();

    act(() => {
      vi.advanceTimersByTime(2100);
    });

    // Mock track is "Midnight City" — same title but from mock
    expect(screen.getByText('Midnight City')).toBeInTheDocument();
  });

  it('live payload replaces mock data after grace period', () => {
    renderPanel();

    act(() => {
      vi.advanceTimersByTime(2100);
    });

    const altPayload: SpotifyStatePayload = {
      authenticated: true,
      track: {
        name: 'Blinding Lights',
        artist: 'The Weeknd',
        album: 'After Hours',
        durationMs: 230_000,
        progressMs: 10_000,
        isPlaying: false,
      },
      device: { name: 'Headphones', type: 'Headphones', volumePercent: 50 },
    };

    act(() => {
      capturedSpotifyListener?.(altPayload);
    });

    expect(screen.getByText('Blinding Lights')).toBeInTheDocument();
    expect(screen.getByText('The Weeknd')).toBeInTheDocument();
  });
});

describe('NowPlayingPanel — transport button commands', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    capturedSpotifyListener = null;
    mockSendFn.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it('play/pause toggle dispatches pause cmd when track is playing', () => {
    renderPanel();

    act(() => {
      capturedSpotifyListener?.(livePayload); // isPlaying: true
    });

    const pauseBtn = screen.getByRole('button', { name: /pause/i });
    fireEvent.click(pauseBtn);

    expect(mockSendFn).toHaveBeenCalledWith('pause', undefined);
  });

  it('play/pause toggle dispatches play cmd when track is paused', () => {
    renderPanel();

    const pausedPayload: SpotifyStatePayload = {
      ...livePayload,
      track: livePayload.track
        ? { ...livePayload.track, isPlaying: false }
        : undefined,
    };

    act(() => {
      capturedSpotifyListener?.(pausedPayload);
    });

    const playBtn = screen.getByRole('button', { name: /play/i });
    fireEvent.click(playBtn);

    expect(mockSendFn).toHaveBeenCalledWith('play', undefined);
  });

  it('previous button dispatches prev cmd', () => {
    renderPanel();

    act(() => {
      capturedSpotifyListener?.(livePayload);
    });

    fireEvent.click(screen.getByRole('button', { name: /previous/i }));
    expect(mockSendFn).toHaveBeenCalledWith('prev', undefined);
  });

  it('next button dispatches next cmd', () => {
    renderPanel();

    act(() => {
      capturedSpotifyListener?.(livePayload);
    });

    fireEvent.click(screen.getByRole('button', { name: /next/i }));
    expect(mockSendFn).toHaveBeenCalledWith('next', undefined);
  });
});

describe('NowPlayingPanel — volume slider debounce', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    capturedSpotifyListener = null;
    mockSendFn.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it('volume slider dispatches volume cmd after 200ms debounce', () => {
    renderPanel();

    act(() => {
      capturedSpotifyListener?.(livePayload);
    });

    const slider = screen.getByRole('slider', { name: /volume/i });

    fireEvent.change(slider, { target: { value: '55' } });

    // Not yet dispatched — within debounce window
    expect(mockSendFn).not.toHaveBeenCalledWith('volume', expect.anything());

    act(() => {
      vi.advanceTimersByTime(200);
    });

    expect(mockSendFn).toHaveBeenCalledWith('volume', 55);
  });

  it('rapid slider changes only dispatch once (debounce)', () => {
    renderPanel();

    act(() => {
      capturedSpotifyListener?.(livePayload);
    });

    const slider = screen.getByRole('slider', { name: /volume/i });

    fireEvent.change(slider, { target: { value: '30' } });
    fireEvent.change(slider, { target: { value: '50' } });
    fireEvent.change(slider, { target: { value: '80' } });

    act(() => {
      vi.advanceTimersByTime(200);
    });

    // Only the last value should be dispatched
    const volumeCalls = mockSendFn.mock.calls.filter(
      (c: unknown[]) => c[0] === 'volume',
    );
    expect(volumeCalls).toHaveLength(1);
    expect(volumeCalls[0][1]).toBe(80);
  });
});

describe('NowPlayingPanel — unauthenticated state', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    capturedSpotifyListener = null;
    mockSendFn.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it('renders VERBINDEN button when authenticated is false', () => {
    renderPanel();

    act(() => {
      capturedSpotifyListener?.(unauthPayload);
    });

    expect(screen.getByRole('button', { name: /log in to spotify/i })).toBeInTheDocument();
    expect(screen.getByText('VERBINDEN')).toBeInTheDocument();
  });

  it('VERBINDEN button opens auth URL in new tab', () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null);
    renderPanel();

    act(() => {
      capturedSpotifyListener?.(unauthPayload);
    });

    fireEvent.click(screen.getByRole('button', { name: /log in to spotify/i }));
    expect(openSpy).toHaveBeenCalledWith(
      'http://127.0.0.1:8766/oauth/spotify/start',
      '_blank',
      'noopener,noreferrer',
    );

    openSpy.mockRestore();
  });

  it('no track fields are rendered when unauthenticated', () => {
    renderPanel();

    act(() => {
      capturedSpotifyListener?.(unauthPayload);
    });

    // Track title from live payload must not appear
    expect(screen.queryByText('Midnight City')).not.toBeInTheDocument();
  });
});

describe('NowPlayingPanel — no active playback (null track)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    capturedSpotifyListener = null;
    mockSendFn.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it('does not crash when authenticated payload has no track', () => {
    expect(() => {
      render(<NowPlayingPanel />);
      act(() => {
        capturedSpotifyListener?.(noTrackPayload);
      });
    }).not.toThrow();
  });

  it('shows NO ACTIVE PLAYBACK when authenticated but no track', () => {
    renderPanel();

    act(() => {
      capturedSpotifyListener?.(noTrackPayload);
    });

    expect(screen.getByText(/NO ACTIVE PLAYBACK/i)).toBeInTheDocument();
  });
});

describe('NowPlayingPanel — compact mode', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    capturedSpotifyListener = null;
    mockSendFn.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it('renders track title in compact mode', () => {
    renderPanel('compact');

    act(() => {
      capturedSpotifyListener?.(livePayload);
    });

    expect(screen.getByText('Midnight City')).toBeInTheDocument();
  });

  it('play/pause button works in compact mode', () => {
    renderPanel('compact');

    act(() => {
      capturedSpotifyListener?.(livePayload);
    });

    const pauseBtn = screen.getByRole('button', { name: /pause/i });
    fireEvent.click(pauseBtn);

    expect(mockSendFn).toHaveBeenCalledWith('pause', undefined);
  });
});
