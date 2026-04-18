/**
 * useSettings — Vitest unit tests.
 *
 * Tests cover:
 *   - Loading defaults when localStorage is empty
 *   - Reading persisted values from localStorage on init
 *   - Clamping panelOpacity to [0.5, 1.0]
 *   - All individual setters persist to localStorage
 *   - Safari private-mode: does not throw when localStorage throws
 */
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useSettings } from '../useSettings';

// ---------------------------------------------------------------------------
// localStorage mock
// ---------------------------------------------------------------------------

const localStorageMock: Record<string, string> = {};

beforeEach(() => {
  // Clear in-memory storage before each test
  Object.keys(localStorageMock).forEach((k) => {
    delete localStorageMock[k];
  });

  vi.spyOn(Storage.prototype, 'getItem').mockImplementation((key) =>
    localStorageMock[key] ?? null,
  );
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation((key, value) => {
    localStorageMock[key] = String(value);
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useSettings', () => {
  it('returns defaults when localStorage is empty', () => {
    const { result } = renderHook(() => useSettings());
    expect(result.current.settings.panelOpacity).toBe(1.0);
    expect(result.current.settings.autoSpeakClaude).toBe(true);
    expect(result.current.settings.pushToTalk).toBe(false);
    expect(result.current.settings.micDeviceId).toBe('');
  });

  it('reads persisted values from localStorage on init', () => {
    localStorageMock['jarvis.panelOpacity'] = '0.7';
    localStorageMock['jarvis.autoSpeakClaude'] = 'false';
    localStorageMock['jarvis.pushToTalk'] = 'true';
    localStorageMock['jarvis.micDeviceId'] = 'device-abc';

    const { result } = renderHook(() => useSettings());
    expect(result.current.settings.panelOpacity).toBeCloseTo(0.7);
    expect(result.current.settings.autoSpeakClaude).toBe(false);
    expect(result.current.settings.pushToTalk).toBe(true);
    expect(result.current.settings.micDeviceId).toBe('device-abc');
  });

  it('clamps panelOpacity below 0.5 up to 0.5', () => {
    localStorageMock['jarvis.panelOpacity'] = '0.1';
    const { result } = renderHook(() => useSettings());
    expect(result.current.settings.panelOpacity).toBe(0.5);
  });

  it('clamps panelOpacity above 1.0 down to 1.0', () => {
    localStorageMock['jarvis.panelOpacity'] = '2.5';
    const { result } = renderHook(() => useSettings());
    expect(result.current.settings.panelOpacity).toBe(1.0);
  });

  it('setPanelOpacity updates state and writes to localStorage', () => {
    const { result } = renderHook(() => useSettings());
    act(() => {
      result.current.setPanelOpacity(0.75);
    });
    expect(result.current.settings.panelOpacity).toBeCloseTo(0.75);
    expect(localStorageMock['jarvis.panelOpacity']).toBe('0.75');
  });

  it('setPanelOpacity clamps value to valid range', () => {
    const { result } = renderHook(() => useSettings());
    act(() => {
      result.current.setPanelOpacity(0.0);
    });
    expect(result.current.settings.panelOpacity).toBe(0.5);
    act(() => {
      result.current.setPanelOpacity(1.5);
    });
    expect(result.current.settings.panelOpacity).toBe(1.0);
  });

  it('setAutoSpeakClaude toggles and persists', () => {
    const { result } = renderHook(() => useSettings());
    act(() => {
      result.current.setAutoSpeakClaude(false);
    });
    expect(result.current.settings.autoSpeakClaude).toBe(false);
    expect(localStorageMock['jarvis.autoSpeakClaude']).toBe('false');
  });

  it('setPushToTalk toggles and persists', () => {
    const { result } = renderHook(() => useSettings());
    act(() => {
      result.current.setPushToTalk(true);
    });
    expect(result.current.settings.pushToTalk).toBe(true);
    expect(localStorageMock['jarvis.pushToTalk']).toBe('true');
  });

  it('setMicDeviceId updates and persists', () => {
    const { result } = renderHook(() => useSettings());
    act(() => {
      result.current.setMicDeviceId('my-device-id');
    });
    expect(result.current.settings.micDeviceId).toBe('my-device-id');
    expect(localStorageMock['jarvis.micDeviceId']).toBe('my-device-id');
  });

  it('does not throw when localStorage.setItem throws (private mode)', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError');
    });
    const { result } = renderHook(() => useSettings());
    // Should not throw even if storage is denied
    expect(() => {
      act(() => {
        result.current.setPanelOpacity(0.8);
      });
    }).not.toThrow();
    // State still updates in memory
    expect(result.current.settings.panelOpacity).toBeCloseTo(0.8);
  });

  it('does not throw when localStorage.getItem throws', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('SecurityError');
    });
    expect(() => {
      renderHook(() => useSettings());
    }).not.toThrow();
  });
});
