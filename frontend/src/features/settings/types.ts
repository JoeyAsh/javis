/**
 * Shared types for the settings feature.
 * No runtime logic — pure TypeScript shapes.
 */

export type OrbStyle = 'css' | 'threejs';

export interface JarvisSettings {
    panelOpacity: number;
    autoSpeakClaude: boolean;
    pushToTalk: boolean;
    micDeviceId: string;
    heartbeatEnabled: boolean;
    orbStyle: OrbStyle;
}

/** Repos config returned by and sent to /api/config/repos */
export interface ReposConfig {
    github: string[];
    gitlab: string[];
}

export type SectionId = 'audio' | 'display' | 'voice' | 'repositories' | 'persona';

export type SaveStatus = 'idle' | 'saving' | 'saved' | 'error';
