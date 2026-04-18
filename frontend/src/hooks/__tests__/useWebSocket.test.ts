/**
 * Tests for error-suppression logic in useWebSocket.
 *
 * Strategy: replace window.WebSocket with a MockWebSocket that exposes the
 * event handlers so tests can fire onerror / onopen manually without a real
 * network connection.
 */
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useWebSocket } from '../useWebSocket';

// ---------------------------------------------------------------------------
// Mock WebSocket
// ---------------------------------------------------------------------------

interface MockWsInstance {
  onopen: ((ev: Event) => void) | null;
  onclose: ((ev: CloseEvent) => void) | null;
  onerror: ((ev: Event) => void) | null;
  onmessage: ((ev: MessageEvent) => void) | null;
  readyState: number;
  close: () => void;
  send: (data: string) => void;
}

// Holds the most-recently created mock instance so tests can reach its handlers.
let latestMockWs: MockWsInstance | null = null;

class MockWebSocket implements MockWsInstance {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;

  readyState = MockWebSocket.CONNECTING;
  onopen: ((ev: Event) => void) | null = null;
  onclose: ((ev: CloseEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;

  constructor(_url: string) {
    latestMockWs = this;
  }

  close(): void {
    this.readyState = MockWebSocket.CLOSED;
    // Fire onclose so the hook schedules a reconnect.
    if (this.onclose) {
      this.onclose(new CloseEvent('close'));
    }
  }

  send(_data: string): void {
    // no-op in tests
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fireError(ws: MockWsInstance): void {
  if (ws.onerror) {
    ws.onerror(new Event('error'));
  }
}

function fireOpen(ws: MockWsInstance): void {
  ws.readyState = MockWebSocket.OPEN;
  if (ws.onopen) {
    ws.onopen(new Event('open'));
  }
}

// ---------------------------------------------------------------------------
// Test suite
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// barge_in message handling
// ---------------------------------------------------------------------------

describe('useWebSocket — barge_in handling', () => {
  let warnSpy: ReturnType<typeof vi.spyOn>;
  let errorSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal('WebSocket', MockWebSocket);
    latestMockWs = null;
    warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    errorSpy = vi.spyOn(console, 'error').mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('barge_in message clears audioQueue and sets orbState to listening', async () => {
    const { result } = renderHook(() => useWebSocket());

    // Open the connection.
    const ws = latestMockWs as MockWsInstance;
    act(() => {
      fireOpen(ws);
    });

    // Register a stop-audio callback to track if it's called.
    let stopCalled = false;
    result.current.registerStopAudio(() => {
      stopCalled = true;
    });

    // Simulate audio arriving first so the queue is non-empty.
    act(() => {
      if (ws.onmessage) {
        ws.onmessage(
          new MessageEvent('message', {
            data: JSON.stringify({ type: 'audio', data: 'abc123', text: 'hello' }),
          }),
        );
      }
    });

    expect(result.current.audioQueue).toHaveLength(1);

    // Now simulate barge_in.
    act(() => {
      if (ws.onmessage) {
        ws.onmessage(
          new MessageEvent('message', { data: JSON.stringify({ type: 'barge_in' }) }),
        );
      }
    });

    // Audio queue must be cleared.
    expect(result.current.audioQueue).toHaveLength(0);
    // Stop callback must have been invoked.
    expect(stopCalled).toBe(true);
    // Orb state must be listening.
    expect(result.current.orbState).toBe('listening');

    // Suppress unused spy warnings.
    void warnSpy;
    void errorSpy;
  });

  it('backchannel audio message enqueues with volume 0.3', () => {
    const { result } = renderHook(() => useWebSocket());

    const ws = latestMockWs as MockWsInstance;
    act(() => {
      fireOpen(ws);
    });

    act(() => {
      if (ws.onmessage) {
        ws.onmessage(
          new MessageEvent('message', {
            data: JSON.stringify({
              type: 'audio',
              data: 'mhm_base64',
              text: '',
              channel: 'backchannel',
            }),
          }),
        );
      }
    });

    expect(result.current.audioQueue).toHaveLength(1);
    expect(result.current.audioQueue[0]).toMatchObject({ data: 'mhm_base64', volume: 0.3 });
  });

  it('regular audio message enqueues with volume 1.0', () => {
    const { result } = renderHook(() => useWebSocket());

    const ws = latestMockWs as MockWsInstance;
    act(() => {
      fireOpen(ws);
    });

    act(() => {
      if (ws.onmessage) {
        ws.onmessage(
          new MessageEvent('message', {
            data: JSON.stringify({ type: 'audio', data: 'hello_base64', text: 'Hello' }),
          }),
        );
      }
    });

    expect(result.current.audioQueue).toHaveLength(1);
    expect(result.current.audioQueue[0]).toMatchObject({ data: 'hello_base64', volume: 1.0 });
  });
});

// ---------------------------------------------------------------------------
// Helper: fire a WS message
// ---------------------------------------------------------------------------
function fireMessage(ws: MockWsInstance, data: unknown): void {
  if (ws.onmessage) {
    ws.onmessage(new MessageEvent('message', { data: JSON.stringify(data) }));
  }
}

// ---------------------------------------------------------------------------
// tool_call — working state
// ---------------------------------------------------------------------------

describe('useWebSocket — tool_call / working state', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal('WebSocket', MockWebSocket);
    latestMockWs = null;
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('tool_call started → orbState becomes working', () => {
    const { result } = renderHook(() => useWebSocket());
    const ws = latestMockWs as MockWsInstance;
    act(() => { fireOpen(ws); });

    act(() => {
      fireMessage(ws, {
        type: 'tool_call',
        payload: { state: 'started', tool_name: 'Read', summary: 'Lese config.yaml' },
      });
    });

    expect(result.current.orbState).toBe('working');
    expect(result.current.currentToolSummary).toBe('Lese config.yaml');
  });

  it('tool_call finished (counter back to 0) → orbState leaves working', () => {
    const { result } = renderHook(() => useWebSocket());
    const ws = latestMockWs as MockWsInstance;
    act(() => { fireOpen(ws); });

    act(() => {
      fireMessage(ws, {
        type: 'tool_call',
        payload: { state: 'started', tool_name: 'Bash', summary: 'Run ls' },
      });
    });
    expect(result.current.orbState).toBe('working');

    act(() => {
      fireMessage(ws, {
        type: 'tool_call',
        payload: { state: 'finished', tool_name: 'Bash', summary: '' },
      });
    });

    // No audio queued, backend state is idle → should resolve to idle.
    expect(result.current.orbState).toBe('idle');
    expect(result.current.currentToolSummary).toBeNull();
  });

  it('two nested tool calls — orb stays working until both finish', () => {
    const { result } = renderHook(() => useWebSocket());
    const ws = latestMockWs as MockWsInstance;
    act(() => { fireOpen(ws); });

    act(() => {
      fireMessage(ws, {
        type: 'tool_call',
        payload: { state: 'started', tool_name: 'Read', summary: 'Read A' },
      });
    });
    act(() => {
      fireMessage(ws, {
        type: 'tool_call',
        payload: { state: 'started', tool_name: 'Glob', summary: 'Glob B' },
      });
    });

    expect(result.current.orbState).toBe('working');

    act(() => {
      fireMessage(ws, {
        type: 'tool_call',
        payload: { state: 'finished', tool_name: 'Read', summary: '' },
      });
    });

    // Still working — second call in flight.
    expect(result.current.orbState).toBe('working');

    act(() => {
      fireMessage(ws, {
        type: 'tool_call',
        payload: { state: 'finished', tool_name: 'Glob', summary: '' },
      });
    });

    expect(result.current.orbState).toBe('idle');
  });

  it('tool call started while audio queue is non-empty → working overrides speaking', () => {
    const { result } = renderHook(() => useWebSocket());
    const ws = latestMockWs as MockWsInstance;
    act(() => { fireOpen(ws); });

    // Enqueue audio first.
    act(() => {
      fireMessage(ws, { type: 'audio', data: 'abc123', text: 'hi' });
    });
    expect(result.current.orbState).toBe('speaking');

    // Tool call arrives while audio is queued.
    act(() => {
      fireMessage(ws, {
        type: 'tool_call',
        payload: { state: 'started', tool_name: 'Write', summary: 'Write file' },
      });
    });

    // working has higher priority than speaking.
    expect(result.current.orbState).toBe('working');
  });
});

// ---------------------------------------------------------------------------
// speaking / idle handoff anchored to audio queue
// ---------------------------------------------------------------------------

describe('useWebSocket — speaking/idle audio handoff', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal('WebSocket', MockWebSocket);
    latestMockWs = null;
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('backend status idle while audio queue has items → orb stays speaking', () => {
    const { result } = renderHook(() => useWebSocket());
    const ws = latestMockWs as MockWsInstance;
    act(() => { fireOpen(ws); });

    // Two audio frames queued.
    act(() => {
      fireMessage(ws, { type: 'audio', data: 'clip1', text: '' });
      fireMessage(ws, { type: 'audio', data: 'clip2', text: '' });
    });
    expect(result.current.audioQueue).toHaveLength(2);

    // Backend says idle — but audio is still queued.
    act(() => {
      fireMessage(ws, { type: 'status', state: 'idle' });
    });

    // Orb must stay speaking.
    expect(result.current.orbState).toBe('speaking');
  });

  it('orb transitions to idle after all audio consumed and isAudioPlaying=false', () => {
    const { result } = renderHook(() => useWebSocket());
    const ws = latestMockWs as MockWsInstance;
    act(() => { fireOpen(ws); });

    act(() => {
      fireMessage(ws, { type: 'audio', data: 'clip1', text: '' });
      fireMessage(ws, { type: 'audio', data: 'clip2', text: '' });
    });

    // Backend sends idle early.
    act(() => {
      fireMessage(ws, { type: 'status', state: 'idle' });
    });
    expect(result.current.orbState).toBe('speaking');

    // Consume first clip.
    act(() => { result.current.consumeAudio(); });
    expect(result.current.orbState).toBe('speaking');

    // Consume second clip.
    act(() => { result.current.consumeAudio(); });

    // Audio queue empty + isAudioPlaying=false (never set to true in this test) → idle.
    expect(result.current.orbState).toBe('idle');
  });

  it('orb stays speaking while notifyAudioPlaying=true even after queue empties', () => {
    const { result } = renderHook(() => useWebSocket());
    const ws = latestMockWs as MockWsInstance;
    act(() => { fireOpen(ws); });

    act(() => {
      fireMessage(ws, { type: 'audio', data: 'clip1', text: '' });
    });

    // Simulate the audio player starting playback.
    act(() => { result.current.notifyAudioPlaying(true); });

    // Backend says idle.
    act(() => {
      fireMessage(ws, { type: 'status', state: 'idle' });
    });

    // Consume from the WS queue (audio still playing via analyser).
    act(() => { result.current.consumeAudio(); });

    // Queue is empty but audio is playing — must stay speaking.
    expect(result.current.orbState).toBe('speaking');

    // Audio finishes.
    act(() => { result.current.notifyAudioPlaying(false); });

    // Now both conditions clear → idle.
    expect(result.current.orbState).toBe('idle');
  });
});

// ---------------------------------------------------------------------------
// Mail state subscriptions
// ---------------------------------------------------------------------------

describe('useWebSocket — mail WS subscriptions', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal('WebSocket', MockWebSocket);
    latestMockWs = null;
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('subscribeMailState receives payload from mail_state message', () => {
    const { result } = renderHook(() => useWebSocket());
    const ws = latestMockWs as MockWsInstance;
    act(() => { fireOpen(ws); });

    const received: unknown[] = [];
    act(() => {
      result.current.subscribeMailState((payload) => {
        received.push(payload);
      });
    });

    act(() => {
      fireMessage(ws, {
        type: 'mail_state',
        payload: {
          messages: [
            {
              id: 'msg-1',
              sender: 'Test Sender',
              subject: 'Hello',
              preview: 'preview text',
              receivedAt: new Date().toISOString(),
              isVip: false,
              unread: true,
            },
          ],
          unread_count: 1,
        },
      });
    });

    expect(received).toHaveLength(1);
    expect((received[0] as { unread_count: number }).unread_count).toBe(1);
  });

  it('subscribeEmailDraftPreview receives payload from email_draft_preview message', () => {
    const { result } = renderHook(() => useWebSocket());
    const ws = latestMockWs as MockWsInstance;
    act(() => { fireOpen(ws); });

    const received: unknown[] = [];
    act(() => {
      result.current.subscribeEmailDraftPreview((payload) => {
        received.push(payload);
      });
    });

    act(() => {
      fireMessage(ws, {
        type: 'email_draft_preview',
        payload: {
          draft_id: 'draft-1',
          to: 'alice@example.com',
          subject: 'Test subject',
          body_preview: 'This is the body.',
          created_at: new Date().toISOString(),
        },
      });
    });

    expect(received).toHaveLength(1);
    expect((received[0] as { to: string }).to).toBe('alice@example.com');
  });

  it('subscribeEmailSendDone receives payload from email_send_done message', () => {
    const { result } = renderHook(() => useWebSocket());
    const ws = latestMockWs as MockWsInstance;
    act(() => { fireOpen(ws); });

    const received: unknown[] = [];
    act(() => {
      result.current.subscribeEmailSendDone((payload) => {
        received.push(payload);
      });
    });

    act(() => {
      fireMessage(ws, {
        type: 'email_send_done',
        payload: {
          draft_id: 'draft-1',
          success: true,
          message_id: 'sent-msg-42',
        },
      });
    });

    expect(received).toHaveLength(1);
    expect((received[0] as { success: boolean }).success).toBe(true);
  });

  it('subscribeMailState unsubscribe removes listener', () => {
    const { result } = renderHook(() => useWebSocket());
    const ws = latestMockWs as MockWsInstance;
    act(() => { fireOpen(ws); });

    const received: unknown[] = [];
    let unsub: (() => void) | undefined;

    act(() => {
      unsub = result.current.subscribeMailState((payload) => {
        received.push(payload);
      });
    });

    // Unsubscribe before message arrives
    act(() => {
      unsub?.();
    });

    act(() => {
      fireMessage(ws, {
        type: 'mail_state',
        payload: { messages: [], unread_count: 0 },
      });
    });

    expect(received).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// Spotify state subscriptions
// ---------------------------------------------------------------------------

describe('useWebSocket — spotify_state subscriptions', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal('WebSocket', MockWebSocket);
    latestMockWs = null;
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('subscribeSpotifyState receives payload from spotify_state message', () => {
    const { result } = renderHook(() => useWebSocket());
    const ws = latestMockWs as MockWsInstance;
    act(() => { fireOpen(ws); });

    const received: unknown[] = [];
    act(() => {
      result.current.subscribeSpotifyState((payload) => {
        received.push(payload);
      });
    });

    act(() => {
      fireMessage(ws, {
        type: 'spotify_state',
        payload: {
          authenticated: true,
          track: {
            name: 'Midnight City',
            artist: 'M83',
            album: 'Hurry Up',
            durationMs: 241_000,
            progressMs: 113_000,
            isPlaying: true,
          },
          device: { name: 'Studio Monitors', type: 'Speaker', volumePercent: 72 },
        },
      });
    });

    expect(received).toHaveLength(1);
    expect((received[0] as { authenticated: boolean }).authenticated).toBe(true);
  });

  it('subscribeSpotifyState receives unauthenticated payload', () => {
    const { result } = renderHook(() => useWebSocket());
    const ws = latestMockWs as MockWsInstance;
    act(() => { fireOpen(ws); });

    const received: unknown[] = [];
    act(() => {
      result.current.subscribeSpotifyState((payload) => {
        received.push(payload);
      });
    });

    act(() => {
      fireMessage(ws, {
        type: 'spotify_state',
        payload: { authenticated: false },
      });
    });

    expect(received).toHaveLength(1);
    expect((received[0] as { authenticated: boolean }).authenticated).toBe(false);
  });

  it('subscribeSpotifyState unsubscribe removes listener', () => {
    const { result } = renderHook(() => useWebSocket());
    const ws = latestMockWs as MockWsInstance;
    act(() => { fireOpen(ws); });

    const received: unknown[] = [];
    let unsub: (() => void) | undefined;

    act(() => {
      unsub = result.current.subscribeSpotifyState((payload) => {
        received.push(payload);
      });
    });

    act(() => { unsub?.(); });

    act(() => {
      fireMessage(ws, {
        type: 'spotify_state',
        payload: { authenticated: true },
      });
    });

    expect(received).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// sendSpotifyCmd
// ---------------------------------------------------------------------------

describe('useWebSocket — sendSpotifyCmd', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal('WebSocket', MockWebSocket);
    latestMockWs = null;
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('sendSpotifyCmd sends correct spotify_cmd JSON when WS is open', () => {
    const { result } = renderHook(() => useWebSocket());
    const ws = latestMockWs as MockWsInstance;
    const sendSpy = vi.spyOn(ws, 'send');
    act(() => { fireOpen(ws); });

    act(() => {
      result.current.sendSpotifyCmd('pause');
    });

    expect(sendSpy).toHaveBeenCalledTimes(1);
    const sent = JSON.parse(sendSpy.mock.calls[0][0] as string) as {
      type: string;
      payload: { action: string };
    };
    expect(sent.type).toBe('spotify_cmd');
    expect(sent.payload.action).toBe('pause');
  });

  it('sendSpotifyCmd includes value for volume action', () => {
    const { result } = renderHook(() => useWebSocket());
    const ws = latestMockWs as MockWsInstance;
    const sendSpy = vi.spyOn(ws, 'send');
    act(() => { fireOpen(ws); });

    act(() => {
      result.current.sendSpotifyCmd('volume', 65);
    });

    const sent = JSON.parse(sendSpy.mock.calls[0][0] as string) as {
      type: string;
      payload: { action: string; value: number };
    };
    expect(sent.payload.action).toBe('volume');
    expect(sent.payload.value).toBe(65);
  });

  it('sendSpotifyCmd no-ops when WS is not open', () => {
    const { result } = renderHook(() => useWebSocket());
    const ws = latestMockWs as MockWsInstance;
    const sendSpy = vi.spyOn(ws, 'send');
    // Do NOT open — ws stays CONNECTING

    act(() => {
      result.current.sendSpotifyCmd('next');
    });

    expect(sendSpy).not.toHaveBeenCalled();
  });
});

describe('useWebSocket — error suppression', () => {
  let debugSpy: ReturnType<typeof vi.spyOn>;
  let warnSpy: ReturnType<typeof vi.spyOn>;
  let errorSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal('WebSocket', MockWebSocket);
    latestMockWs = null;

    debugSpy = vi.spyOn(console, 'debug').mockImplementation(() => undefined);
    warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    errorSpy = vi.spyOn(console, 'error').mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  // -------------------------------------------------------------------------
  // Rule 1: initial connect phase — all errors suppressed to debug
  // -------------------------------------------------------------------------

  it('errors before any successful open always use console.debug', () => {
    renderHook(() => useWebSocket());

    const ws = latestMockWs as MockWsInstance;

    // Fire 5 errors without ever opening — all should be debug, never warn
    fireError(ws);
    vi.advanceTimersByTime(1100);
    const ws2 = latestMockWs as MockWsInstance;
    fireError(ws2);
    vi.advanceTimersByTime(2100);
    const ws3 = latestMockWs as MockWsInstance;
    fireError(ws3);
    vi.advanceTimersByTime(4100);
    const ws4 = latestMockWs as MockWsInstance;
    fireError(ws4);
    vi.advanceTimersByTime(8100);
    const ws5 = latestMockWs as MockWsInstance;
    fireError(ws5);

    expect(debugSpy).toHaveBeenCalledTimes(5);
    expect(warnSpy).not.toHaveBeenCalled();
    expect(errorSpy).not.toHaveBeenCalledWith(expect.stringContaining('[ws]'));
  });

  // -------------------------------------------------------------------------
  // Rule 2: reconnect phase — first 3 errors debug, 4th → single warn
  // -------------------------------------------------------------------------

  it('first 3 reconnect errors after an open use console.debug', () => {
    renderHook(() => useWebSocket());

    // Establish a successful connection first (makes hasEverOpened = true)
    const ws0 = latestMockWs as MockWsInstance;
    fireOpen(ws0);

    // Now fire 3 errors (reconnect phase)
    fireError(ws0);
    vi.advanceTimersByTime(1100);
    const ws1 = latestMockWs as MockWsInstance;
    fireError(ws1);
    vi.advanceTimersByTime(2100);
    const ws2 = latestMockWs as MockWsInstance;
    fireError(ws2);

    expect(debugSpy).toHaveBeenCalledTimes(3);
    expect(warnSpy).not.toHaveBeenCalled();
    expect(errorSpy).not.toHaveBeenCalledWith(expect.stringContaining('[ws]'));
  });

  it('4th reconnect error produces exactly one console.warn', () => {
    renderHook(() => useWebSocket());

    // Establish a successful connection first
    const ws0 = latestMockWs as MockWsInstance;
    fireOpen(ws0);

    // 3 errors below threshold
    fireError(ws0);
    vi.advanceTimersByTime(1100);
    const ws1 = latestMockWs as MockWsInstance;
    fireError(ws1);
    vi.advanceTimersByTime(2100);
    const ws2 = latestMockWs as MockWsInstance;
    fireError(ws2);
    vi.advanceTimersByTime(4100);
    // 4th error — crosses threshold
    const ws3 = latestMockWs as MockWsInstance;
    fireError(ws3);

    expect(warnSpy).toHaveBeenCalledTimes(1);
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringMatching(/\[ws\] backend unreachable after 4 attempts/),
    );
    expect(errorSpy).not.toHaveBeenCalledWith(expect.stringContaining('[ws]'));
  });

  it('5th and 6th reconnect errors do NOT produce additional warns', () => {
    renderHook(() => useWebSocket());

    const ws0 = latestMockWs as MockWsInstance;
    fireOpen(ws0);

    // 4 errors to reach + cross threshold
    fireError(ws0);
    vi.advanceTimersByTime(1100);
    const ws1 = latestMockWs as MockWsInstance;
    fireError(ws1);
    vi.advanceTimersByTime(2100);
    const ws2 = latestMockWs as MockWsInstance;
    fireError(ws2);
    vi.advanceTimersByTime(4100);
    const ws3 = latestMockWs as MockWsInstance;
    fireError(ws3); // warn fires here (4th)
    vi.advanceTimersByTime(8100);
    const ws4 = latestMockWs as MockWsInstance;
    fireError(ws4); // no additional warn
    vi.advanceTimersByTime(16100);
    const ws5 = latestMockWs as MockWsInstance;
    fireError(ws5); // no additional warn

    expect(warnSpy).toHaveBeenCalledTimes(1);
  });

  // -------------------------------------------------------------------------
  // Rule 3: successful open resets counters
  // -------------------------------------------------------------------------

  it('after a successful open, error counter resets so next error goes back to debug', () => {
    renderHook(() => useWebSocket());

    const ws0 = latestMockWs as MockWsInstance;
    // First open — sets hasEverOpened, resets counter
    fireOpen(ws0);

    // Drive 3 errors to bring counter to threshold boundary
    fireError(ws0);
    vi.advanceTimersByTime(1100);
    const ws1 = latestMockWs as MockWsInstance;
    fireError(ws1);
    vi.advanceTimersByTime(2100);
    const ws2 = latestMockWs as MockWsInstance;
    fireError(ws2);

    // Re-connect succeeds — counter resets
    vi.advanceTimersByTime(4100);
    const ws3 = latestMockWs as MockWsInstance;
    fireOpen(ws3);

    // Next error should be debug (counter = 1, ≤ 3)
    fireError(ws3);

    // 3 debug calls from the first error wave + 1 debug after reset = 4 total
    expect(debugSpy).toHaveBeenCalledTimes(4);
    expect(warnSpy).not.toHaveBeenCalled();
  });
});
