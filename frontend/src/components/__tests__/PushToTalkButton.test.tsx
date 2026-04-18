/**
 * PushToTalkButton — Vitest + RTL tests.
 *
 * Tests cover:
 *   - Not rendered when enabled=false
 *   - Rendered with idle PTT label when enabled=true
 *   - Shows 'REC' label while holding (mousedown)
 *   - Returns to 'PTT' after release flash period
 *   - aria-pressed reflects holding state
 *   - Does not throw when wsRef is null
 */
import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { PushToTalkButton } from '../PushToTalkButton';
import type React from 'react';

// ---------------------------------------------------------------------------
// Minimal AudioContext mock
// ---------------------------------------------------------------------------

const mockProcessor = {
  connect: vi.fn(),
  disconnect: vi.fn(),
  onaudioprocess: null as ((e: AudioProcessingEvent) => void) | null,
};

const mockSource = { connect: vi.fn(), disconnect: vi.fn() };
const mockGain = { gain: { value: 1 }, connect: vi.fn(), disconnect: vi.fn() };

const mockAudioCtx = {
  sampleRate: 16000,
  state: 'running' as AudioContextState,
  resume: vi.fn().mockResolvedValue(undefined),
  close: vi.fn(),
  createScriptProcessor: vi.fn().mockReturnValue(mockProcessor),
  createMediaStreamSource: vi.fn().mockReturnValue(mockSource),
  createGain: vi.fn().mockReturnValue(mockGain),
  destination: {} as AudioDestinationNode,
};

const mockStream = { getTracks: () => [{ stop: vi.fn() }] };

beforeEach(() => {
  Object.defineProperty(globalThis.navigator, 'mediaDevices', {
    writable: true,
    configurable: true,
    value: {
      getUserMedia: vi.fn().mockResolvedValue(mockStream),
    },
  });
  (globalThis as unknown as Record<string, unknown>)['AudioContext'] =
    vi.fn().mockImplementation(() => ({ ...mockAudioCtx }));
});

afterEach(() => {
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeWsRef(readyState = WebSocket.OPEN): React.RefObject<WebSocket | null> {
  const ws = { readyState, send: vi.fn() } as unknown as WebSocket;
  return { current: ws };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('PushToTalkButton', () => {
  it('renders nothing when enabled=false', () => {
    const { container } = render(<PushToTalkButton enabled={false} wsRef={makeWsRef()} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders PTT label when enabled=true', () => {
    render(<PushToTalkButton enabled wsRef={makeWsRef()} />);
    expect(screen.getByText('PTT')).toBeTruthy();
  });

  it('has accessible push-to-talk label', () => {
    render(<PushToTalkButton enabled wsRef={makeWsRef()} />);
    expect(screen.getByLabelText(/push to talk/i)).toBeTruthy();
  });

  it('shows REC label while mouse is held down', async () => {
    render(<PushToTalkButton enabled wsRef={makeWsRef()} />);
    const btn = screen.getByLabelText(/push to talk/i);
    await act(async () => {
      fireEvent.mouseDown(btn);
      // Allow the async startCapture to settle
      await new Promise<void>((resolve) => setTimeout(resolve, 10));
    });
    expect(screen.getByText('REC')).toBeTruthy();
    expect(btn.getAttribute('aria-pressed')).toBe('true');
  });

  it('returns to PTT label after mouseup + flash period', async () => {
    vi.useFakeTimers();
    render(<PushToTalkButton enabled wsRef={makeWsRef()} />);
    const btn = screen.getByLabelText(/push to talk/i);

    await act(async () => {
      fireEvent.mouseDown(btn);
      await Promise.resolve();
    });

    act(() => {
      fireEvent.mouseUp(btn);
    });

    // Advance past the 300ms flash timer
    act(() => {
      vi.advanceTimersByTime(400);
    });

    expect(screen.getByText('PTT')).toBeTruthy();
    expect(btn.getAttribute('aria-pressed')).toBe('false');
    vi.useRealTimers();
  });

  it('does not throw when wsRef.current is null', async () => {
    const nullRef: React.RefObject<WebSocket | null> = { current: null };
    render(<PushToTalkButton enabled wsRef={nullRef} />);
    const btn = screen.getByLabelText(/push to talk/i);
    await act(async () => {
      fireEvent.mouseDown(btn);
      await new Promise<void>((resolve) => setTimeout(resolve, 10));
    });
    // No crash — PTT started without a WS connection
    expect(screen.getByText('REC')).toBeTruthy();
  });
});
