/**
 * useAudioEngine hook — Vitest unit tests.
 *
 * All external dependencies (AudioEngine, localStorage, document events) are
 * mocked so no real audio hardware or network calls occur.
 *
 * Tests reflect the actual implementation including:
 *   - Full Batch 2 state machine
 *   - state_change fired on every orb transition except:
 *       - first render (prev === null)
 *       - same-state transitions
 *       - listening transitions while wake-guard is active
 */

import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// ---------------------------------------------------------------------------
// Shared spy registry — the mock class delegates to these.
// ---------------------------------------------------------------------------

const spies = {
    resumeContext: vi.fn().mockResolvedValue(undefined),
    playOneShot: vi.fn(),
    play: vi.fn(),
    stop: vi.fn(),
    setMuted: vi.fn(),
    setDucking: vi.fn(),
    destroy: vi.fn(),
};

let mockIsMuted = false;

vi.mock('@core/audio/audioEngine', () => {
    class AudioEngine {
        resumeContext(...args: Parameters<typeof spies.resumeContext>) {
            return spies.resumeContext(...args);
        }
        playOneShot(...args: Parameters<typeof spies.playOneShot>) {
            return spies.playOneShot(...args);
        }
        play(...args: Parameters<typeof spies.play>) {
            return spies.play(...args);
        }
        stop(...args: Parameters<typeof spies.stop>) {
            return spies.stop(...args);
        }
        setMuted(...args: Parameters<typeof spies.setMuted>) {
            return spies.setMuted(...args);
        }
        setDucking(...args: Parameters<typeof spies.setDucking>) {
            return spies.setDucking(...args);
        }
        destroy(...args: Parameters<typeof spies.destroy>) {
            return spies.destroy(...args);
        }
        get isMuted() {
            return mockIsMuted;
        }
    }

    // Singleton that the hook imports via getAudioEngine().
    let __singleton: InstanceType<typeof AudioEngine> | null = null;

    return {
        AudioEngine,
        getAudioEngine: () => {
            if (__singleton === null) {
                __singleton = new AudioEngine();
            }
            return __singleton;
        },
        __resetAudioEngineSingleton: () => {
            if (__singleton !== null) {
                try {
                    __singleton.destroy();
                } catch { /* ignore */ }
                __singleton = null;
            }
        },
    };
});

import { useAudioEngine } from '../useAudioEngine';
import { __resetAudioEngineSingleton } from '@core/audio';

// ---------------------------------------------------------------------------
// matchMedia mock
// ---------------------------------------------------------------------------

beforeEach(() => {
    Object.defineProperty(window, 'matchMedia', {
        writable: true,
        configurable: true,
        value: vi.fn().mockReturnValue({ matches: false }),
    });
    vi.useFakeTimers();
});

// ---------------------------------------------------------------------------
// localStorage mock
// ---------------------------------------------------------------------------

let localStorageStore: Record<string, string> = {};

beforeEach(() => {
    localStorageStore = {};
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(
        (key: string) => localStorageStore[key] ?? null,
    );
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation((key: string, value: string) => {
        localStorageStore[key] = value;
    });
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation((key: string) => {
        delete localStorageStore[key];
    });
});

afterEach(() => {
    vi.useRealTimers();
    // Reset the singleton FIRST (while the current spies are still in place) so
    // the destroy() call from the reset is recorded on the old spy, not the
    // freshly-created one that the next test will inspect.
    __resetAudioEngineSingleton();
    vi.clearAllMocks();
    mockIsMuted = false;
    spies.resumeContext = vi.fn().mockResolvedValue(undefined);
    spies.playOneShot = vi.fn();
    spies.play = vi.fn();
    spies.stop = vi.fn();
    spies.setMuted = vi.fn();
    spies.setDucking = vi.fn();
    spies.destroy = vi.fn();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useAudioEngine — first user gesture', () => {
    it('pointerdown on document calls engine.resumeContext()', async () => {
        renderHook(() => useAudioEngine('idle', true));

        await act(async () => {
            document.dispatchEvent(new PointerEvent('pointerdown'));
            await Promise.resolve();
        });

        expect(spies.resumeContext).toHaveBeenCalled();
    });

    it('pointerdown plays boot sound after context is resumed', async () => {
        renderHook(() => useAudioEngine('idle', true));

        await act(async () => {
            document.dispatchEvent(new PointerEvent('pointerdown'));
            await Promise.resolve();
        });

        expect(spies.playOneShot).toHaveBeenCalledWith('boot');
    });

    it('second pointerdown does NOT re-trigger boot (listener is { once: true })', async () => {
        renderHook(() => useAudioEngine('idle', true));

        await act(async () => {
            document.dispatchEvent(new PointerEvent('pointerdown'));
            await Promise.resolve();
        });

        const bootCallsAfterFirst = spies.playOneShot.mock.calls.filter(
            (c) => c[0] === 'boot',
        ).length;

        await act(async () => {
            document.dispatchEvent(new PointerEvent('pointerdown'));
            await Promise.resolve();
        });

        const bootCallsAfterSecond = spies.playOneShot.mock.calls.filter(
            (c) => c[0] === 'boot',
        ).length;

        expect(bootCallsAfterSecond).toBe(bootCallsAfterFirst);
    });
});

describe('useAudioEngine — orbState loop management', () => {
    it('orbState=thinking → play("thinking")', async () => {
        await act(async () => {
            const { rerender } = renderHook(
                ({ orb }: { orb: 'idle' | 'thinking' }) => useAudioEngine(orb, true),
                { initialProps: { orb: 'idle' as 'idle' | 'thinking' } },
            );
            rerender({ orb: 'thinking' });
        });

        expect(spies.play).toHaveBeenCalledWith('thinking');
    });

    it('orbState=thinking → stops idle_pulse and heartbeat', async () => {
        await act(async () => {
            const { rerender } = renderHook(
                ({ orb }: { orb: 'idle' | 'thinking' }) => useAudioEngine(orb, true),
                { initialProps: { orb: 'idle' as 'idle' | 'thinking' } },
            );
            rerender({ orb: 'thinking' });
        });

        expect(spies.stop).toHaveBeenCalledWith('idle_pulse');
        expect(spies.stop).toHaveBeenCalledWith('heartbeat');
    });

    it('orbState=working → play("working") and stops thinking/scan loops', async () => {
        await act(async () => {
            const { rerender } = renderHook(
                ({ orb }: { orb: 'idle' | 'working' }) => useAudioEngine(orb, true),
                { initialProps: { orb: 'idle' as 'idle' | 'working' } },
            );
            rerender({ orb: 'working' });
        });

        expect(spies.play).toHaveBeenCalledWith('working');
        expect(spies.stop).toHaveBeenCalledWith('thinking');
        expect(spies.stop).toHaveBeenCalledWith('scan');
    });

    it('transition from thinking to idle → play("ambient")', async () => {
        const { rerender } = renderHook(
            ({ orb }: { orb: 'idle' | 'thinking' }) => useAudioEngine(orb, true),
            { initialProps: { orb: 'idle' as 'idle' | 'thinking' } },
        );

        await act(async () => {
            rerender({ orb: 'thinking' });
        });

        spies.play.mockClear();

        await act(async () => {
            rerender({ orb: 'idle' });
        });

        expect(spies.play).toHaveBeenCalledWith('ambient');
    });

    it('listening → setDucking(true) and playOneShot("mic_open")', async () => {
        await act(async () => {
            const { rerender } = renderHook(
                ({ orb }: { orb: 'idle' | 'listening' }) => useAudioEngine(orb, true),
                { initialProps: { orb: 'idle' as 'idle' | 'listening' } },
            );
            rerender({ orb: 'listening' });
        });

        expect(spies.setDucking).toHaveBeenCalledWith(true);
        expect(spies.playOneShot).toHaveBeenCalledWith('mic_open');
    });

    it('speaking → setDucking(true) and playOneShot("speech_start")', async () => {
        await act(async () => {
            const { rerender } = renderHook(
                ({ orb }: { orb: 'idle' | 'speaking' }) => useAudioEngine(orb, true),
                { initialProps: { orb: 'idle' as 'idle' | 'speaking' } },
            );
            rerender({ orb: 'speaking' });
        });

        expect(spies.setDucking).toHaveBeenCalledWith(true);
        expect(spies.playOneShot).toHaveBeenCalledWith('speech_start');
    });

    it('transition from idle to thinking triggers thinking loop start', async () => {
        const { rerender } = renderHook(
            ({ orb }: { orb: 'idle' | 'thinking' }) => useAudioEngine(orb, true),
            { initialProps: { orb: 'idle' as 'idle' | 'thinking' } },
        );

        const playCallsBefore = spies.play.mock.calls.length;

        await act(async () => {
            rerender({ orb: 'thinking' });
        });

        const newPlayCalls = spies.play.mock.calls.slice(playCallsBefore);
        expect(newPlayCalls.some((c) => c[0] === 'thinking')).toBe(true);
    });
});

describe('useAudioEngine — state_change on every non-wake-guarded transition', () => {
    it('does NOT fire state_change on initial render (prev === null)', async () => {
        await act(async () => {
            renderHook(() => useAudioEngine('idle', true));
        });
        const stateChangeCalls = spies.playOneShot.mock.calls.filter(
            (c) => c[0] === 'state_change',
        );
        expect(stateChangeCalls).toHaveLength(0);
    });

    it('idle → thinking fires state_change', async () => {
        const { rerender } = renderHook(
            ({ orb }: { orb: 'idle' | 'thinking' }) => useAudioEngine(orb, true),
            { initialProps: { orb: 'idle' as 'idle' | 'thinking' } },
        );

        spies.playOneShot.mockClear();

        await act(async () => {
            rerender({ orb: 'thinking' });
        });

        expect(spies.playOneShot).toHaveBeenCalledWith('state_change');
    });

    it('idle → listening fires state_change (wake-guard is inactive by default)', async () => {
        const { rerender } = renderHook(
            ({ orb }: { orb: 'idle' | 'listening' }) => useAudioEngine(orb, true),
            { initialProps: { orb: 'idle' as 'idle' | 'listening' } },
        );

        spies.playOneShot.mockClear();

        await act(async () => {
            rerender({ orb: 'listening' });
        });

        expect(spies.playOneShot).toHaveBeenCalledWith('state_change');
    });

    it('thinking → working fires state_change', async () => {
        const { rerender } = renderHook(
            ({ orb }: { orb: 'idle' | 'thinking' | 'working' }) => useAudioEngine(orb, true),
            { initialProps: { orb: 'idle' as 'idle' | 'thinking' | 'working' } },
        );

        await act(async () => {
            rerender({ orb: 'thinking' });
        });

        spies.playOneShot.mockClear();

        await act(async () => {
            rerender({ orb: 'working' });
        });

        expect(spies.playOneShot).toHaveBeenCalledWith('state_change');
    });

    it('listening → thinking fires state_change', async () => {
        const { rerender } = renderHook(
            ({ orb }: { orb: 'idle' | 'listening' | 'thinking' }) => useAudioEngine(orb, true),
            { initialProps: { orb: 'idle' as 'idle' | 'listening' | 'thinking' } },
        );

        await act(async () => {
            rerender({ orb: 'listening' });
        });

        spies.playOneShot.mockClear();

        await act(async () => {
            rerender({ orb: 'thinking' });
        });

        expect(spies.playOneShot).toHaveBeenCalledWith('state_change');
    });

    it('same-state update does NOT fire state_change', async () => {
        const { rerender } = renderHook(
            ({ orb }: { orb: 'idle' }) => useAudioEngine(orb, true),
            { initialProps: { orb: 'idle' as 'idle' } },
        );

        spies.playOneShot.mockClear();

        await act(async () => {
            rerender({ orb: 'idle' });
        });

        const stateChangeCalls = spies.playOneShot.mock.calls.filter(
            (c) => c[0] === 'state_change',
        );
        expect(stateChangeCalls).toHaveLength(0);
    });
});

describe('useAudioEngine — duck toggling', () => {
    it('entering listening → setDucking(true)', async () => {
        await act(async () => {
            const { rerender } = renderHook(
                ({ orb }: { orb: 'idle' | 'listening' }) => useAudioEngine(orb, true),
                { initialProps: { orb: 'idle' as 'idle' | 'listening' } },
            );
            rerender({ orb: 'listening' });
        });

        expect(spies.setDucking).toHaveBeenCalledWith(true);
    });

    it('listening → idle: setDucking(false) is called', async () => {
        const { rerender } = renderHook(
            ({ orb }: { orb: 'idle' | 'listening' }) => useAudioEngine(orb, true),
            { initialProps: { orb: 'idle' as 'idle' | 'listening' } },
        );

        await act(async () => {
            rerender({ orb: 'listening' });
        });

        spies.setDucking.mockClear();

        await act(async () => {
            rerender({ orb: 'idle' });
        });

        expect(spies.setDucking).toHaveBeenCalledWith(false);
    });
});

describe('useAudioEngine — toggleMute()', () => {
    it('toggleMute() calls engine.setMuted(true) when currently unmuted', async () => {
        mockIsMuted = false;
        const { result } = renderHook(() => useAudioEngine('idle', true));

        await act(async () => {
            result.current.toggleMute();
        });

        expect(spies.setMuted).toHaveBeenCalledWith(true);
    });

    it('toggleMute() writes new value to localStorage', async () => {
        mockIsMuted = false;
        const { result } = renderHook(() => useAudioEngine('idle', true));

        await act(async () => {
            result.current.toggleMute();
        });

        expect(Storage.prototype.setItem).toHaveBeenCalledWith('jarvis.sfx.muted', 'true');
    });

    it('toggling twice restores original mute state', async () => {
        mockIsMuted = false;
        const { result } = renderHook(() => useAudioEngine('idle', true));

        await act(async () => {
            result.current.toggleMute();
        });
        mockIsMuted = true;

        await act(async () => {
            result.current.toggleMute();
        });

        expect(spies.setMuted).toHaveBeenLastCalledWith(false);
        expect(Storage.prototype.setItem).toHaveBeenLastCalledWith('jarvis.sfx.muted', 'false');
    });
});

describe('useAudioEngine — localStorage persistence', () => {
    it('on mount, reads jarvis.sfx.muted=true and applies setMuted(true)', async () => {
        localStorageStore['jarvis.sfx.muted'] = 'true';

        await act(async () => {
            renderHook(() => useAudioEngine('idle', true));
        });

        expect(spies.setMuted).toHaveBeenCalledWith(true);
    });

    it('on mount, reads jarvis.sfx.muted=false and applies setMuted(false)', async () => {
        localStorageStore['jarvis.sfx.muted'] = 'false';

        await act(async () => {
            renderHook(() => useAudioEngine('idle', true));
        });

        expect(spies.setMuted).toHaveBeenCalledWith(false);
    });

    it('localStorage unavailable (getItem throws) → falls back to false, does not throw', async () => {
        vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
            throw new Error('SecurityError');
        });

        expect(() => renderHook(() => useAudioEngine('idle', true))).not.toThrow();
    });

    it('localStorage setItem unavailable → toggleMute does not throw', async () => {
        vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
            throw new Error('QuotaExceededError');
        });
        mockIsMuted = false;

        const { result } = renderHook(() => useAudioEngine('idle', true));

        await expect(
            act(async () => {
                result.current.toggleMute();
            }),
        ).resolves.toBeUndefined();
    });
});

describe('useAudioEngine — visibilitychange', () => {
    it('visibilitychange to visible calls resumeContext()', async () => {
        renderHook(() => useAudioEngine('idle', true));

        await act(async () => {
            Object.defineProperty(document, 'visibilityState', {
                writable: true,
                configurable: true,
                value: 'visible',
            });
            document.dispatchEvent(new Event('visibilitychange'));
            await Promise.resolve();
        });

        expect(spies.resumeContext).toHaveBeenCalled();
    });

    it('visibilitychange to hidden does NOT call resumeContext()', async () => {
        renderHook(() => useAudioEngine('idle', true));
        spies.resumeContext.mockClear();

        await act(async () => {
            Object.defineProperty(document, 'visibilityState', {
                writable: true,
                configurable: true,
                value: 'hidden',
            });
            document.dispatchEvent(new Event('visibilitychange'));
            await Promise.resolve();
        });

        expect(spies.resumeContext).not.toHaveBeenCalled();
    });
});

describe('useAudioEngine — cleanup on unmount', () => {
    it('unmounting the hook stops all active loops (does NOT destroy the singleton)', async () => {
        const { unmount } = renderHook(() => useAudioEngine('idle', true));

        unmount();

        // The engine is a module singleton — destroy() must NOT be called on unmount.
        expect(spies.destroy).not.toHaveBeenCalled();

        // All loop events must be stopped so the next remount starts clean.
        const stoppedEvents = spies.stop.mock.calls.map((c) => c[0] as string);
        expect(stoppedEvents).toContain('ambient');
        expect(stoppedEvents).toContain('scan');
        expect(stoppedEvents).toContain('thinking');
        expect(stoppedEvents).toContain('working');
        expect(stoppedEvents).toContain('idle_pulse');
        expect(stoppedEvents).toContain('heartbeat');
        expect(stoppedEvents).toContain('drag_move');
        expect(stoppedEvents).toContain('resize');
    });
});

describe('useAudioEngine — playOneShot passthrough', () => {
    it('playOneShot() forwards event to engine.playOneShot()', async () => {
        const { result } = renderHook(() => useAudioEngine('idle', true));

        await act(async () => {
            result.current.playOneShot('click');
        });

        expect(spies.playOneShot).toHaveBeenCalledWith('click');
    });
});

describe('useAudioEngine — play/stop passthrough', () => {
    it('play() forwards event to engine.play()', async () => {
        const { result } = renderHook(() => useAudioEngine('idle', true));

        await act(async () => {
            result.current.play('drag_move');
        });

        expect(spies.play).toHaveBeenCalledWith('drag_move');
    });

    it('stop() forwards event to engine.stop()', async () => {
        const { result } = renderHook(() => useAudioEngine('idle', true));

        await act(async () => {
            result.current.stop('drag_move');
        });

        expect(spies.stop).toHaveBeenCalledWith('drag_move');
    });
});
