export interface ControlsClusterProps {
    idle: boolean;
    onToggleIdle: () => void;
    onResetLayout: () => void;
    onOpenSettings: () => void;
    micMuted: boolean;
    onToggleMicMute: () => void;
    sfxMuted: boolean;
    onToggleSfxMute: () => void;
}
