/**
 * React integration for the JARVIS Web Audio Engine — Batch 2 full state machine.
 *
 * Responsibilities:
 *   - Create and destroy the AudioEngine singleton per component mount.
 *   - Resume the AudioContext on the first user gesture (pointer/key).
 *   - Play `boot` one-shot after context is resumed.
 *   - Full state machine: transitions between idle / listening / thinking /
 *     working / speaking fire appropriate one-shots and loop management.
 *   - Duck ambient loops during listening / speaking.
 *   - Idle timeout: after 30 s idle → start idle_pulse (+ heartbeat when enabled).
 *   - Disconnect SFX gate: play disconnect only after 5 s of disconnection.
 *   - Offline SFX gate: play offline after 3 s of no WS message.
 *   - Shutdown: fire `shutdown` on beforeunload.
 *   - Persist mute preference to localStorage.
 *   - Handle `visibilitychange` to resume a suspended context on tab focus.
 *   - Fire `state_change` on every orb state transition except:
 *       - First render (prev === null)
 *       - Same-state transitions
 *       - listening transitions while wake-guard is active
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { getAudioEngine } from './audioEngine';
import type { AudioEngine } from './audioEngine';
import type { SfxEvent } from './config';
import type { AppOrbState } from '../../types';

const STORAGE_KEY = 'jarvis.sfx.muted';

/** After this many ms idle → play idle_pulse (and heartbeat if enabled). */
const IDLE_TIMEOUT_MS = 30_000;

/** Wait this long after disconnect before firing the disconnect SFX. */
const DISCONNECT_SFX_GATE_MS = 5_000;

/** Wait this long after going offline before firing the offline SFX. */
const OFFLINE_DELAY_MS = 3_000;

/** Suppress duplicate state_change events within this window after wake. */
const WAKE_GUARD_MS = 500;

function readStoredMute(): boolean {
    try {
        return localStorage.getItem(STORAGE_KEY) === 'true';
    } catch {
        return false;
    }
}

function writeStoredMute(value: boolean): void {
    try {
        localStorage.setItem(STORAGE_KEY, String(value));
    } catch {
        // Storage might be full or blocked — degrade silently.
    }
}

export interface UseAudioEngineReturn {
    isMuted: boolean;
    toggleMute: () => void;
    playOneShot: (event: SfxEvent) => void;
    play: (event: SfxEvent) => void;
    stop: (event: SfxEvent) => void;
    engine: AudioEngine;
}

/**
 * Hook that owns the lifecycle of the AudioEngine and exposes a minimal
 * control surface to the rest of the app.
 *
 * @param orbState - Current app orb state; drives the full SFX state machine.
 * @param connected - Whether the WebSocket is connected; drives disconnect/offline SFX.
 * @param heartbeatEnabled - Whether to play the heartbeat loop during idle timeout.
 */
export function useAudioEngine(
    orbState: AppOrbState,
    connected: boolean,
    heartbeatEnabled = false,
): UseAudioEngineReturn {
    // Module-level singleton: all mounts (incl. StrictMode double-invoke) share
    // the same AudioContext, which must not be closed between mounts.
    const engineRef = useRef<AudioEngine>(getAudioEngine());

    const [isMuted, setIsMuted] = useState<boolean>(readStoredMute);

    // Apply initial mute state to the engine right away.
    useEffect(() => {
        engineRef.current.setMuted(isMuted);
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    // ── State-machine refs ────────────────────────────────────────────────────

    const bootFiredRef = useRef(false);
    // null = "not yet seen a state" (used to detect first render in resume handler).
    const prevOrbStateRef = useRef<AppOrbState | null>(null);
    const wakeGuardActiveRef = useRef(false);

    // Timer handles.
    const idleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const disconnectSfxTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const offlineTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Keep heartbeatEnabled in a ref so the idle timeout closure sees the latest value.
    const heartbeatEnabledRef = useRef(heartbeatEnabled);
    useEffect(() => {
        heartbeatEnabledRef.current = heartbeatEnabled;
    }, [heartbeatEnabled]);

    // ── Helpers ───────────────────────────────────────────────────────────────

    const clearIdleTimer = useCallback(() => {
        if (idleTimerRef.current !== null) {
            clearTimeout(idleTimerRef.current);
            idleTimerRef.current = null;
        }
    }, []);

    const stopIdleLoops = useCallback(() => {
        clearIdleTimer();
        engineRef.current.stop('idle_pulse');
        engineRef.current.stop('heartbeat');
    }, [clearIdleTimer]);

    const startIdleTimer = useCallback(() => {
        clearIdleTimer();
        idleTimerRef.current = setTimeout(() => {
            const engine = engineRef.current;
            if (!engine) return;
            engine.play('idle_pulse');
            if (heartbeatEnabledRef.current) engine.play('heartbeat');
        }, IDLE_TIMEOUT_MS);
    }, [clearIdleTimer]);

    // ── User-gesture → resume context ─────────────────────────────────────────

    useEffect(() => {
        const engine = engineRef.current;
        if (!engine) return;

        const resume = (): void => {
            void engine.resumeContext().then(() => {
                if (!bootFiredRef.current) {
                    bootFiredRef.current = true;
                    engine.playOneShot('boot');
                }
                // Kick the current orb-state's intended loops now that the context is
                // live. Without this, loops started before the first gesture are silent
                // (launchLoop bails out when ctx.state === 'suspended').
                const s = prevOrbStateRef.current;
                if (s === 'idle' || s === 'follow_up' || s === null) {
                    engine.play('ambient');
                } else if (s === 'listening') {
                    engine.play('scan');
                    engine.setDucking(true);
                } else if (s === 'thinking') {
                    engine.play('thinking');
                    engine.play('scan');
                } else if (s === 'working') {
                    engine.play('working');
                }
                // 'speaking' has no loops to replay.
            });
        };

        document.addEventListener('pointerdown', resume, { once: true });
        document.addEventListener('keydown', resume, { once: true });

        return () => {
            document.removeEventListener('pointerdown', resume);
            document.removeEventListener('keydown', resume);
        };
    }, []);

    // ── visibilitychange → resume suspended context ───────────────────────────

    useEffect(() => {
        const engine = engineRef.current;
        if (!engine) return;

        const onVisible = (): void => {
            if (document.visibilityState === 'visible') {
                void engine.resumeContext();
            }
        };

        document.addEventListener('visibilitychange', onVisible);
        return () => {
            document.removeEventListener('visibilitychange', onVisible);
        };
    }, []);

    // ── Shutdown on beforeunload ──────────────────────────────────────────────

    useEffect(() => {
        const onUnload = (): void => {
            engineRef.current.playOneShot('shutdown');
        };
        window.addEventListener('beforeunload', onUnload);
        return () => {
            window.removeEventListener('beforeunload', onUnload);
        };
    }, []);

    // ── orbState → full state machine ─────────────────────────────────────────

    useEffect(() => {
        const engine = engineRef.current;
        if (!engine) return;

        const prev = prevOrbStateRef.current;
        prevOrbStateRef.current = orbState;

        // Skip if state hasn't changed.
        if (prev === orbState) return;

        // Fire state_change on every real transition, but:
        //   - not on first render (prev === null)
        //   - not when entering listening with wake-guard active
        if (prev !== null) {
            const suppressStateChange = orbState === 'listening' && wakeGuardActiveRef.current;
            if (!suppressStateChange) {
                engine.playOneShot('state_change');
            }
        }

        // ── Exit handlers for the previous state ─────────────────────────────
        if (prev === 'listening') {
            engine.setDucking(false);
            engine.playOneShot('mic_close');
        } else if (prev === 'speaking') {
            engine.setDucking(false);
            const isBargeIn = orbState === 'listening';
            if (isBargeIn) {
                engine.playOneShot('barge_in');
            } else {
                engine.playOneShot('speech_end');
            }
        } else if (prev === 'thinking') {
            engine.stop('thinking');
            engine.stop('scan');
        } else if (prev === 'working') {
            engine.stop('working');
            engine.stop('thinking');
            engine.stop('scan');
        }

        // ── Entry handlers for the new state ─────────────────────────────────
        if (orbState === 'idle' || orbState === 'follow_up') {
            stopIdleLoops();
            engine.play('ambient');
            startIdleTimer();
        } else if (orbState === 'listening') {
            stopIdleLoops();
            engine.setDucking(true);
            engine.playOneShot('mic_open');
        } else if (orbState === 'thinking') {
            stopIdleLoops();
            engine.play('thinking');
            engine.play('scan');
        } else if (orbState === 'working') {
            stopIdleLoops();
            engine.stop('thinking');
            engine.stop('scan');
            engine.play('working');
        } else if (orbState === 'speaking') {
            stopIdleLoops();
            engine.setDucking(true);
            engine.playOneShot('speech_start');
        }
    }, [orbState, startIdleTimer, stopIdleLoops]);

    // ── Disconnect / offline SFX gating ──────────────────────────────────────

    useEffect(() => {
        if (!connected) {
            disconnectSfxTimerRef.current = setTimeout(() => {
                engineRef.current.playOneShot('disconnect');
            }, DISCONNECT_SFX_GATE_MS);

            offlineTimerRef.current = setTimeout(() => {
                engineRef.current.playOneShot('offline');
            }, OFFLINE_DELAY_MS);
        } else {
            if (disconnectSfxTimerRef.current !== null) {
                clearTimeout(disconnectSfxTimerRef.current);
                disconnectSfxTimerRef.current = null;
            }
            if (offlineTimerRef.current !== null) {
                clearTimeout(offlineTimerRef.current);
                offlineTimerRef.current = null;
            }
        }

        return () => {
            if (disconnectSfxTimerRef.current !== null) {
                clearTimeout(disconnectSfxTimerRef.current);
                disconnectSfxTimerRef.current = null;
            }
            if (offlineTimerRef.current !== null) {
                clearTimeout(offlineTimerRef.current);
                offlineTimerRef.current = null;
            }
        };
    }, [connected]);

    // ── Heartbeat loop toggling at runtime ────────────────────────────────────

    useEffect(() => {
        // If we're currently idle and in the idle-pulse phase (timer already fired),
        // sync the heartbeat loop with the setting.
        if ((orbState === 'idle' || orbState === 'follow_up') && idleTimerRef.current === null) {
            if (heartbeatEnabled) {
                engineRef.current.play('heartbeat');
            } else {
                engineRef.current.stop('heartbeat');
            }
        }
    }, [heartbeatEnabled, orbState]);

    // ── Cleanup on unmount ────────────────────────────────────────────────────

    useEffect(() => {
        return () => {
            clearIdleTimer();
            // Intentionally do NOT destroy the engine — it is a module singleton
            // shared with any re-mounts (StrictMode double-invoke, route changes).
            // Just stop active loops so a remount starts clean.
            const engine = engineRef.current;
            engine.stop('ambient');
            engine.stop('scan');
            engine.stop('thinking');
            engine.stop('working');
            engine.stop('idle_pulse');
            engine.stop('heartbeat');
            engine.stop('drag_move');
            engine.stop('resize');
            bootFiredRef.current = false;
            prevOrbStateRef.current = null;
        };
    }, [clearIdleTimer]);

    // ── Controls ──────────────────────────────────────────────────────────────

    const toggleMute = useCallback(() => {
        const engine = engineRef.current;
        const next = !engine.isMuted;
        engine.setMuted(next);
        setIsMuted(next);
        writeStoredMute(next);
    }, []);

    const playOneShot = useCallback((event: SfxEvent) => {
        engineRef.current.playOneShot(event);
    }, []);

    const play = useCallback((event: SfxEvent) => {
        engineRef.current.play(event);
    }, []);

    const stop = useCallback((event: SfxEvent) => {
        engineRef.current.stop(event);
    }, []);

    // Silence the unused-variable warning for WAKE_GUARD_MS until the wake
    // message handler (from WS) is wired in a future step.
    void WAKE_GUARD_MS;

    return {
        isMuted,
        toggleMute,
        playOneShot,
        play,
        stop,
        engine: engineRef.current,
    };
}

export default useAudioEngine;
