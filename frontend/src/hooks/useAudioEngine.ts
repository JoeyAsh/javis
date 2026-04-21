/**
 * React integration for the JARVIS Web Audio Engine.
 *
 * Responsibilities:
 *   - Create and destroy the AudioEngine singleton per component mount.
 *   - Resume the AudioContext on the first user gesture (pointer/key).
 *   - Play `boot` one-shot after context is resumed.
 *   - Manage ambient/scan loops based on `orbState`.
 *   - Persist mute preference to localStorage.
 *   - Handle `visibilitychange` to resume a suspended context on tab focus.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { AudioEngine } from '../lib/audioEngine';
import type { SfxEvent } from '../config/audio';
import type { AppOrbState } from '../types';

const STORAGE_KEY = 'jarvis.sfx.muted';

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
  engine: AudioEngine;
}

/**
 * Hook that owns the lifecycle of the AudioEngine and exposes a minimal
 * control surface to the rest of the app.
 *
 * @param orbState - Current app orb state; drives ambient/scan loop management.
 * @param connected - Whether the WebSocket is connected. Reserved for Batch 2
 *   disconnect handling — not yet consumed but kept in the signature so the
 *   call-site in App.tsx doesn't need to change later.
 */
export function useAudioEngine(
  orbState: AppOrbState,
  connected: boolean,
): UseAudioEngineReturn {
  // connected is intentionally unused in Batch 1; Batch 2 will add disconnect handling.
  void connected;
  const engineRef = useRef<AudioEngine | null>(null);

  // Initialise engine once per mount.
  if (engineRef.current === null) {
    engineRef.current = new AudioEngine();
  }

  const [isMuted, setIsMuted] = useState<boolean>(readStoredMute);

  // Apply initial mute state to the engine right away.
  useEffect(() => {
    engineRef.current?.setMuted(isMuted);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Track whether we have already played the boot sound for this session.
  const bootFiredRef = useRef(false);

  // ---- User-gesture → resume context ----------------------------------------

  useEffect(() => {
    const engine = engineRef.current;
    if (!engine) return;

    const resume = (): void => {
      void engine.resumeContext().then(() => {
        if (!bootFiredRef.current) {
          bootFiredRef.current = true;
          engine.playOneShot('boot');
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

  // ---- visibilitychange → resume suspended context --------------------------

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

  // ---- orbState → loop management (Batch 1: ambient + scan) ----------------

  useEffect(() => {
    const engine = engineRef.current;
    if (!engine) return;

    // Batch 1 mapping (detailed event-driven mapping comes in Batch 2 / #34):
    //   thinking / working → play scan loop, stop ambient
    //   anything else      → play ambient loop, stop scan
    if (orbState === 'thinking' || orbState === 'working') {
      engine.stop('ambient');
      engine.play('scan');
    } else {
      engine.stop('scan');
      engine.play('ambient');
    }
  }, [orbState]);

  // ---- Destroy on unmount ---------------------------------------------------

  useEffect(() => {
    const engine = engineRef.current;
    return () => {
      engine?.destroy();
    };
  }, []);

  // ---- Controls ------------------------------------------------------------

  const toggleMute = useCallback(() => {
    const engine = engineRef.current;
    if (!engine) return;
    const next = !engine.isMuted;
    engine.setMuted(next);
    setIsMuted(next);
    writeStoredMute(next);
  }, []);

  const playOneShot = useCallback((event: SfxEvent) => {
    engineRef.current?.playOneShot(event);
  }, []);

  return {
    isMuted,
    toggleMute,
    playOneShot,
    // Stable reference: the engine lives for the full component lifetime.
    engine: engineRef.current,
  };
}

export default useAudioEngine;
