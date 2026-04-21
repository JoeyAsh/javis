/**
 * useSettings — reads and writes all JARVIS settings stored in localStorage.
 *
 * Storage keys:
 *   jarvis.panelOpacity      float 0.5–1.0  (default 1.0)
 *   jarvis.autoSpeakClaude   boolean         (default true)
 *   jarvis.pushToTalk        boolean         (default false)
 *   jarvis.micDeviceId       string          (default '')
 *   jarvis.orbVariant        'classic' | 'hypermodern'  (default 'classic')
 *   jarvis.heartbeatEnabled  boolean         (default false)
 *
 * All writes are wrapped in a try/catch to handle Safari private-mode and
 * other storage-denied environments gracefully.
 */

import { useCallback, useState } from 'react';

export type OrbVariant = 'classic' | 'hypermodern';

export interface JarvisSettings {
  panelOpacity: number;
  autoSpeakClaude: boolean;
  pushToTalk: boolean;
  micDeviceId: string;
  orbVariant: OrbVariant;
  heartbeatEnabled: boolean;
}

const DEFAULTS: JarvisSettings = {
  panelOpacity: 1.0,
  autoSpeakClaude: true,
  pushToTalk: false,
  micDeviceId: '',
  orbVariant: 'classic',
  heartbeatEnabled: false,
};

function safeGet(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeSet(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    // Storage denied (Safari private, quota exceeded) — ignore silently.
  }
}

function loadSettings(): JarvisSettings {
  const opacityRaw = safeGet('jarvis.panelOpacity');
  const autoSpeakRaw = safeGet('jarvis.autoSpeakClaude');
  const pttRaw = safeGet('jarvis.pushToTalk');
  const micRaw = safeGet('jarvis.micDeviceId');
  const orbVariantRaw = safeGet('jarvis.orbVariant');
  const heartbeatRaw = safeGet('jarvis.heartbeatEnabled');

  const panelOpacity =
    opacityRaw !== null
      ? Math.max(0.5, Math.min(1.0, parseFloat(opacityRaw)))
      : DEFAULTS.panelOpacity;
  const autoSpeakClaude =
    autoSpeakRaw !== null ? autoSpeakRaw === 'true' : DEFAULTS.autoSpeakClaude;
  const pushToTalk = pttRaw !== null ? pttRaw === 'true' : DEFAULTS.pushToTalk;
  const micDeviceId = micRaw ?? DEFAULTS.micDeviceId;

  const orbVariant: OrbVariant =
    orbVariantRaw === 'hypermodern' ? 'hypermodern' : DEFAULTS.orbVariant;
  const heartbeatEnabled =
    heartbeatRaw !== null ? heartbeatRaw === 'true' : DEFAULTS.heartbeatEnabled;

  return { panelOpacity, autoSpeakClaude, pushToTalk, micDeviceId, orbVariant, heartbeatEnabled };
}

export interface UseSettingsReturn {
  settings: JarvisSettings;
  setPanelOpacity: (v: number) => void;
  setAutoSpeakClaude: (v: boolean) => void;
  setPushToTalk: (v: boolean) => void;
  setMicDeviceId: (v: string) => void;
  setOrbVariant: (v: OrbVariant) => void;
  setHeartbeatEnabled: (v: boolean) => void;
}

/**
 * Hook that manages persistent JARVIS UI settings via localStorage.
 * Returns the current settings object and individual setters.
 */
export function useSettings(): UseSettingsReturn {
  const [settings, setSettings] = useState<JarvisSettings>(loadSettings);

  const setPanelOpacity = useCallback((v: number) => {
    const clamped = Math.max(0.5, Math.min(1.0, v));
    safeSet('jarvis.panelOpacity', String(clamped));
    setSettings((prev) => ({ ...prev, panelOpacity: clamped }));
  }, []);

  const setAutoSpeakClaude = useCallback((v: boolean) => {
    safeSet('jarvis.autoSpeakClaude', String(v));
    setSettings((prev) => ({ ...prev, autoSpeakClaude: v }));
  }, []);

  const setPushToTalk = useCallback((v: boolean) => {
    safeSet('jarvis.pushToTalk', String(v));
    setSettings((prev) => ({ ...prev, pushToTalk: v }));
  }, []);

  const setMicDeviceId = useCallback((v: string) => {
    safeSet('jarvis.micDeviceId', v);
    setSettings((prev) => ({ ...prev, micDeviceId: v }));
  }, []);

  const setOrbVariant = useCallback((v: OrbVariant) => {
    safeSet('jarvis.orbVariant', v);
    setSettings((prev) => ({ ...prev, orbVariant: v }));
  }, []);

  const setHeartbeatEnabled = useCallback((v: boolean) => {
    safeSet('jarvis.heartbeatEnabled', String(v));
    setSettings((prev) => ({ ...prev, heartbeatEnabled: v }));
  }, []);

  return {
    settings,
    setPanelOpacity,
    setAutoSpeakClaude,
    setPushToTalk,
    setMicDeviceId,
    setOrbVariant,
    setHeartbeatEnabled,
  };
}

export default useSettings;
