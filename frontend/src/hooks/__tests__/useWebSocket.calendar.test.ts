/**
 * Tests for calendar WebSocket message routing in useWebSocket.
 *
 * Strategy: replace window.WebSocket with a MockWebSocket that exposes the
 * onmessage handler so tests can inject raw WS frames. Asserts that
 * calendar_state, calendar_op_preview, and calendar_op_done messages route
 * to the correct subscriber callbacks with the correct payloads.
 */
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useWebSocket } from '../useWebSocket';
import {
  subscribeCalendarStateStream,
  subscribeCalendarOpPreviewStream,
  subscribeCalendarOpDoneStream,
} from '../useWebSocket';
import type { CalendarStateListener, CalendarOpPreviewListener, CalendarOpDoneListener } from '../useWebSocket';

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
    if (this.onclose) {
      this.onclose(new CloseEvent('close'));
    }
  }

  send(_data: string): void {
    // no-op
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function openMockWs(): void {
  if (latestMockWs?.onopen) {
    latestMockWs.readyState = MockWebSocket.OPEN;
    latestMockWs.onopen(new Event('open'));
  }
}

function injectWsMessage(data: unknown): void {
  if (latestMockWs?.onmessage) {
    latestMockWs.onmessage(new MessageEvent('message', { data: JSON.stringify(data) }));
  }
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  latestMockWs = null;
  vi.stubGlobal('WebSocket', MockWebSocket);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// calendar_state routing (via hook subscriber)
// ---------------------------------------------------------------------------

describe('useWebSocket — calendar_state', () => {
  it('routes calendar_state to subscribeCalendarState callback', async () => {
    const received: unknown[] = [];
    const { result } = renderHook(() => useWebSocket());

    let unsub: (() => void) | undefined;
    act(() => {
      unsub = result.current.subscribeCalendarState((p) => received.push(p));
      openMockWs();
    });

    const payload = {
      events: [
        {
          id: 'evt1',
          title: 'Standup',
          start: '2026-04-18T09:00:00Z',
          end: '2026-04-18T09:30:00Z',
          calendar: 'primary',
          location: null,
        },
      ],
      dateLabel: 'Heute',
    };

    act(() => {
      injectWsMessage({ type: 'calendar_state', payload });
    });

    expect(received).toHaveLength(1);
    expect((received[0] as typeof payload).dateLabel).toBe('Heute');
    expect((received[0] as typeof payload).events[0].title).toBe('Standup');

    unsub?.();
  });

  it('does not fire calendar_state callback after unsubscribe', async () => {
    const received: unknown[] = [];
    const { result } = renderHook(() => useWebSocket());

    let unsub: (() => void) | undefined;
    act(() => {
      unsub = result.current.subscribeCalendarState((p) => received.push(p));
      openMockWs();
    });

    // Unsubscribe before message arrives.
    act(() => {
      unsub?.();
    });

    act(() => {
      injectWsMessage({
        type: 'calendar_state',
        payload: { events: [], dateLabel: 'Heute' },
      });
    });

    expect(received).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// calendar_op_done routing (via hook subscriber)
// ---------------------------------------------------------------------------

describe('useWebSocket — calendar_op_done', () => {
  it('routes calendar_op_done to subscribeCalendarOpDone callback', async () => {
    const received: unknown[] = [];
    const { result } = renderHook(() => useWebSocket());

    let unsub: (() => void) | undefined;
    act(() => {
      unsub = result.current.subscribeCalendarOpDone((p) => received.push(p));
      openMockWs();
    });

    const payload = { op: 'create' as const, success: true, event_id: 'new123' };

    act(() => {
      injectWsMessage({ type: 'calendar_op_done', payload });
    });

    expect(received).toHaveLength(1);
    expect((received[0] as typeof payload).success).toBe(true);
    expect((received[0] as typeof payload).event_id).toBe('new123');

    unsub?.();
  });

  it('routes calendar_op_done with success=false (cancel path)', async () => {
    const received: unknown[] = [];
    const { result } = renderHook(() => useWebSocket());

    let unsub: (() => void) | undefined;
    act(() => {
      unsub = result.current.subscribeCalendarOpDone((p) => received.push(p));
      openMockWs();
    });

    act(() => {
      injectWsMessage({
        type: 'calendar_op_done',
        payload: { op: 'delete', success: false, error: 'Abgebrochen' },
      });
    });

    expect(received).toHaveLength(1);
    expect((received[0] as { success: boolean }).success).toBe(false);

    unsub?.();
  });
});

// ---------------------------------------------------------------------------
// calendar_op_preview routing (via hook subscriber)
// ---------------------------------------------------------------------------

describe('useWebSocket — calendar_op_preview', () => {
  it('routes calendar_op_preview to subscribeCalendarOpPreview callback', async () => {
    const received: unknown[] = [];
    const { result } = renderHook(() => useWebSocket());

    let unsub: (() => void) | undefined;
    act(() => {
      unsub = result.current.subscribeCalendarOpPreview((p) => received.push(p));
      openMockWs();
    });

    const payload = {
      op: 'create' as const,
      title: 'Team Meeting',
      start: '2026-04-19T14:00:00Z',
      end: '2026-04-19T15:00:00Z',
      confirm_prompt: "Create 'Team Meeting' tomorrow at 14:00?",
    };

    act(() => {
      injectWsMessage({ type: 'calendar_op_preview', payload });
    });

    expect(received).toHaveLength(1);
    expect((received[0] as typeof payload).op).toBe('create');
    expect((received[0] as typeof payload).title).toBe('Team Meeting');

    unsub?.();
  });
});

// ---------------------------------------------------------------------------
// Standalone stream helpers (subscribeCalendarStateStream etc.)
// ---------------------------------------------------------------------------

describe('subscribeCalendarStateStream — standalone', () => {
  it('fires listener when calendar_state arrives via hook', async () => {
    const received: unknown[] = [];
    const listener: CalendarStateListener = (p) => received.push(p);
    const unsub = subscribeCalendarStateStream(listener);

    renderHook(() => useWebSocket());
    act(() => {
      openMockWs();
    });

    act(() => {
      injectWsMessage({
        type: 'calendar_state',
        payload: {
          events: [
            {
              id: 'live1',
              title: 'Live Standup',
              start: '2026-04-18T10:00:00Z',
              end: '2026-04-18T10:30:00Z',
              calendar: 'primary',
              location: null,
            },
          ],
          dateLabel: 'Heute',
        },
      });
    });

    expect(received).toHaveLength(1);
    expect(
      (received[0] as { events: Array<{ title: string }> }).events[0].title,
    ).toBe('Live Standup');

    unsub();
  });

  it('unsubscribes cleanly without throwing', () => {
    const listener: CalendarStateListener = vi.fn();
    const unsub = subscribeCalendarStateStream(listener);
    expect(() => unsub()).not.toThrow();
    // Calling again is safe (Set.delete is idempotent).
    expect(() => unsub()).not.toThrow();
  });
});

describe('subscribeCalendarOpDoneStream — standalone', () => {
  it('fires listener when calendar_op_done arrives via hook', async () => {
    const received: unknown[] = [];
    const listener: CalendarOpDoneListener = (p) => received.push(p);
    const unsub = subscribeCalendarOpDoneStream(listener);

    renderHook(() => useWebSocket());
    act(() => {
      openMockWs();
    });

    act(() => {
      injectWsMessage({
        type: 'calendar_op_done',
        payload: { op: 'create', success: true, event_id: 'created_xyz' },
      });
    });

    expect(received).toHaveLength(1);
    expect((received[0] as { event_id: string }).event_id).toBe('created_xyz');

    unsub();
  });
});

describe('subscribeCalendarOpPreviewStream — standalone', () => {
  it('fires listener when calendar_op_preview arrives via hook', async () => {
    const received: unknown[] = [];
    const listener: CalendarOpPreviewListener = (p) => received.push(p);
    const unsub = subscribeCalendarOpPreviewStream(listener);

    renderHook(() => useWebSocket());
    act(() => {
      openMockWs();
    });

    act(() => {
      injectWsMessage({
        type: 'calendar_op_preview',
        payload: {
          op: 'delete',
          title: 'Old Meeting',
          start: '2026-04-20T09:00:00Z',
          end: '2026-04-20T09:30:00Z',
          confirm_prompt: "Delete 'Old Meeting'?",
        },
      });
    });

    expect(received).toHaveLength(1);
    expect((received[0] as { op: string }).op).toBe('delete');

    unsub();
  });
});
