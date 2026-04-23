import type { JarvisSettings, OrbStyle } from '../types';

export type { JarvisSettings, OrbStyle };

export interface UseSettingsReturn {
    settings: JarvisSettings;
    setPanelOpacity: (v: number) => void;
    setAutoSpeakClaude: (v: boolean) => void;
    setPushToTalk: (v: boolean) => void;
    setMicDeviceId: (v: string) => void;
    setHeartbeatEnabled: (v: boolean) => void;
    setOrbStyle: (v: OrbStyle) => void;
}
