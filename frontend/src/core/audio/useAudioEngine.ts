/**
 * React integration for the JARVIS Web Audio Engine.
 * Copy of src/lib/audio/useAudioEngine.ts — original remains in place.
 * Imports adjusted for new location within core/audio/.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { getAudioEngine } from './audioEngine';
import type { AudioEngine } from './audioEngine';
import type { SfxEvent } from './config';
import type { AppOrbState } from '@common/types';

const STORAGE_KEY = 'jarvis.sfx.muted';
const IDLE_TIMEOUT_MS = 30_000;
const DISCONNECT_SFX_GATE_MS = 5_000;
const OFFLINE_DELAY_MS = 3_000;

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

export function useAudioEngine(
    orbState: AppOrbState,
    connected: boolean,
    heartbeatEnabled = false,
): UseAudioEngineReturn {
    const engineRef = useRef<AudioEngine>(getAudioEngine());

    const [isMuted, setIsMuted] = useState<boolean>(readStoredMute);

    useEffect(() => {
        engineRef.current.setMuted(isMuted);
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    const bootFiredRef = useRef(false);
    const prevOrbStateRef = useRef<AppOrbState | null>(null);

    const idleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const disconnectSfxTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const offlineTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const heartbeatEnabledRef = useRef(heartbeatEnabled);
    useEffect(() => {
        heartbeatEnabledRef.current = heartbeatEnabled;
    }, [heartbeatEnabled]);

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

    useEffect(() => {
        const engine = engineRef.current;
        if (!engine) return;

        const resume = (): void => {
            void engine.resumeContext().then(() => {
                if (!bootFiredRef.current) {
                    bootFiredRef.current = true;
                    engine.playOneShot('boot');
                }
                const s = prevOrbStateRef.current;
                if (s === 'idle' || s === 'follow_up' || s === null) {
                    engine.play('ambient');
                } else if (s === 'listening') {
                    engine.play('scan');
                    engine.setDucking(true);
                } else if (s === 'thinking') {
                    engine.play('thinking');
                } else if (s === 'working') {
                    engine.play('working');
                }
            });
        };

        document.addEventListener('pointerdown', resume, { once: true });
        document.addEventListener('keydown', resume, { once: true });

        return () => {
            document.removeEventListener('pointerdown', resume);
            document.removeEventListener('keydown', resume);
        };
    }, []);

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

    useEffect(() => {
        const onUnload = (): void => {
            engineRef.current.playOneShot('shutdown');
        };
        window.addEventListener('beforeunload', onUnload);
        return () => {
            window.removeEventListener('beforeunload', onUnload);
        };
    }, []);

    useEffect(() => {
        const engine = engineRef.current;
        if (!engine) return;

        const prev = prevOrbStateRef.current;
        prevOrbStateRef.current = orbState;

        if (prev === orbState) return;

        // state_change fires on every real transition except:
        //   - initial mount (prev === null)
        //   - entering follow_up: it's a soft, continuation state — no jarring
        //     state-change cue; the ambient loop resuming provides the implicit signal.
        if (prev !== null && orbState !== 'follow_up') {
            engine.playOneShot('state_change');
        }

        if (prev === 'listening') {
            engine.setDucking(false);
            engine.playOneShot('mic_close');
        } else if (prev === 'follow_up') {
            // follow_up exit: ambient loop stays alive for the next entry branch to handle.
            // No ducking was active, no scan was running — nothing to clean up here.
        } else if (prev === 'speaking') {
            engine.setDucking(false);
            // Barge-in only when the user literally interrupted: listening arrives while
            // audio was playing. A follow_up transition means audio finished normally —
            // play speech_end so the end-of-speech cue fires reliably.
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

        if (orbState === 'idle') {
            stopIdleLoops();
            engine.play('ambient');
            startIdleTimer();
        } else if (orbState === 'follow_up') {
            // Softer alert-but-relaxed listening window: ambient resumes, scan stops,
            // no idle-pulse timer (we're still actively in a conversation turn),
            // no mic_open SFX (mic is already open from the previous listening state),
            // no state_change cue (suppressed above — ambient loop is the implicit signal).
            stopIdleLoops();
            engine.stop('scan');
            engine.setDucking(false);
            engine.play('ambient');
        } else if (orbState === 'listening') {
            stopIdleLoops();
            engine.setDucking(true);
            engine.playOneShot('mic_open');
        } else if (orbState === 'thinking') {
            stopIdleLoops();
            engine.play('thinking');
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

    useEffect(() => {
        // Heartbeat is an idle-only ambient — don't play it during follow_up
        // (which is an active conversation window, not a true resting state).
        if (orbState === 'idle' && idleTimerRef.current === null) {
            if (heartbeatEnabled) {
                engineRef.current.play('heartbeat');
            } else {
                engineRef.current.stop('heartbeat');
            }
        }
    }, [heartbeatEnabled, orbState]);

    useEffect(() => {
        return () => {
            clearIdleTimer();
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
