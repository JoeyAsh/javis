/**
 * useLogStream — unit tests.
 *
 * Tests:
 * 1. Initial state: empty lines array.
 * 2. Subscribes to log_line stream on mount.
 * 3. Appends incoming log lines to the buffer.
 * 4. Respects maxLines ring-buffer limit.
 * 5. clear() empties the buffer.
 * 6. Unsubscribes on unmount.
 */
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// ---------------------------------------------------------------------------
// Mock the standalone subscribeLogLineStream helper
// ---------------------------------------------------------------------------

vi.mock('../useWebSocket', () => {
  let _stored: ((payload: import('../../types').LogLinePayload) => void) | null = null;

  return {
    subscribeLogLineStream: vi.fn((listener) => {
      _stored = listener;
      return () => {
        _stored = null;
      };
    }),
    // Expose helper so tests can fire the listener
    __fireLogLine: (payload: import('../../types').LogLinePayload) => {
      if (_stored) _stored(payload);
    },
  };
});

import { subscribeLogLineStream } from '../useWebSocket';
import { useLogStream } from '../useLogStream';
import type { LogLinePayload } from '../../types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const mod = await import('../useWebSocket') as any;
const fireLogLine = (payload: LogLinePayload) => mod.__fireLogLine(payload);

function makeEntry(overrides: Partial<LogLinePayload> = {}): LogLinePayload {
  return {
    timestamp: Date.now(),
    level: 'INFO',
    module: 'ws_server',
    message: 'Test log line',
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useLogStream', () => {
  beforeEach(() => {
    vi.mocked(subscribeLogLineStream).mockClear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('starts with empty lines', () => {
    const { result } = renderHook(() => useLogStream());
    expect(result.current.lines).toHaveLength(0);
  });

  it('calls subscribeLogLineStream on mount', () => {
    renderHook(() => useLogStream());
    expect(subscribeLogLineStream).toHaveBeenCalledTimes(1);
  });

  it('appends incoming log lines', () => {
    const { result } = renderHook(() => useLogStream());

    act(() => {
      fireLogLine(makeEntry({ message: 'hello' }));
    });
    act(() => {
      fireLogLine(makeEntry({ message: 'world' }));
    });

    expect(result.current.lines).toHaveLength(2);
    expect(result.current.lines[0].message).toBe('hello');
    expect(result.current.lines[1].message).toBe('world');
  });

  it('respects maxLines ring-buffer limit', () => {
    const { result } = renderHook(() => useLogStream(3));

    act(() => {
      fireLogLine(makeEntry({ message: 'A' }));
      fireLogLine(makeEntry({ message: 'B' }));
      fireLogLine(makeEntry({ message: 'C' }));
      fireLogLine(makeEntry({ message: 'D' }));
    });

    expect(result.current.lines).toHaveLength(3);
    // Oldest (A) was evicted; B, C, D remain
    expect(result.current.lines[0].message).toBe('B');
    expect(result.current.lines[2].message).toBe('D');
  });

  it('clear() empties the buffer', () => {
    const { result } = renderHook(() => useLogStream());

    act(() => {
      fireLogLine(makeEntry());
      fireLogLine(makeEntry());
    });
    expect(result.current.lines).toHaveLength(2);

    act(() => {
      result.current.clear();
    });
    expect(result.current.lines).toHaveLength(0);
  });

  it('unsubscribes on unmount', () => {
    const unsub = vi.fn();
    vi.mocked(subscribeLogLineStream).mockReturnValueOnce(unsub);

    const { unmount } = renderHook(() => useLogStream());
    unmount();

    expect(unsub).toHaveBeenCalledTimes(1);
  });
});
