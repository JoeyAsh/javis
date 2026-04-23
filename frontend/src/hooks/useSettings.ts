/**
 * useSettings — reads and writes all JARVIS settings stored in localStorage.
 *
 * Storage keys:
 *   jarvis.panelOpacity      float 0.5–1.0  (default 1.0)
 *   jarvis.autoSpeakClaude   boolean         (default true)
 *   jarvis.pushToTalk        boolean         (default false)
 *   jarvis.micDeviceId       string          (default '')
 *   jarvis.heartbeatEnabled  boolean         (default false)
 *   jarvis.orbStyle          'css'|'threejs' (default 'css')
 *
 * All writes are wrapped in a try/catch to handle Safari private-mode and
 * other storage-denied environments gracefully.
 */

import { useCallback, useState } from 'react';

export type OrbStyle = 'css' | 'threejs';

export interface JarvisSettings {
    panelOpacity: number;
    autoSpeakClaude: boolean;
    pushToTalk: boolean;
    micDeviceId: string;
    heartbeatEnabled: boolean;
    orbStyle: OrbStyle;
}

const DEFAULTS: JarvisSettings = {
    panelOpacity: 1.0,
    autoSpeakClaude: true,
    pushToTalk: true,
    micDeviceId: '',
    heartbeatEnabled: false,
    orbStyle: 'css',
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
    const heartbeatRaw = safeGet('jarvis.heartbeatEnabled');
    const orbStyleRaw = safeGet('jarvis.orbStyle');

    const panelOpacity =
        opacityRaw !== null
            ? Math.max(0.5, Math.min(1.0, parseFloat(opacityRaw)))
            : DEFAULTS.panelOpacity;
    const autoSpeakClaude =
        autoSpeakRaw !== null ? autoSpeakRaw === 'true' : DEFAULTS.autoSpeakClaude;
    const pushToTalk = pttRaw !== null ? pttRaw === 'true' : DEFAULTS.pushToTalk;
    const micDeviceId = micRaw ?? DEFAULTS.micDeviceId;
    const heartbeatEnabled =
        heartbeatRaw !== null ? heartbeatRaw === 'true' : DEFAULTS.heartbeatEnabled;
    const orbStyle: OrbStyle =
        orbStyleRaw === 'threejs' ? 'threejs' : DEFAULTS.orbStyle;

    return { panelOpacity, autoSpeakClaude, pushToTalk, micDeviceId, heartbeatEnabled, orbStyle };
}

export interface UseSettingsReturn {
    settings: JarvisSettings;
    setPanelOpacity: (v: number) => void;
    setAutoSpeakClaude: (v: boolean) => void;
    setPushToTalk: (v: boolean) => void;
    setMicDeviceId: (v: string) => void;
    setHeartbeatEnabled: (v: boolean) => void;
    setOrbStyle: (v: OrbStyle) => void;
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

    const setHeartbeatEnabled = useCallback((v: boolean) => {
        safeSet('jarvis.heartbeatEnabled', String(v));
        setSettings((prev) => ({ ...prev, heartbeatEnabled: v }));
    }, []);

    const setOrbStyle = useCallback((v: OrbStyle) => {
        safeSet('jarvis.orbStyle', v);
        setSettings((prev) => ({ ...prev, orbStyle: v }));
    }, []);

    return {
        settings,
        setPanelOpacity,
        setAutoSpeakClaude,
        setPushToTalk,
        setMicDeviceId,
        setHeartbeatEnabled,
        setOrbStyle,
    };
}

export default useSettings;
