export type MicPermission = 'unknown' | 'granted' | 'denied';

export interface AudioSectionProps {
    micDeviceId: string;
    onMicDeviceChange: (id: string) => void;
    pushToTalk: boolean;
    onPushToTalkChange: (v: boolean) => void;
}
