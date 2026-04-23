export interface VoiceSectionProps {
    autoSpeakClaude: boolean;
    onAutoSpeakChange: (v: boolean) => void;
    heartbeatEnabled: boolean;
    onHeartbeatChange: (v: boolean) => void;
}
