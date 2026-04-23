export interface AudioSectionProps {
    micDeviceId: string;
    onMicDeviceChange: (id: string) => void;
    pushToTalk: boolean;
    onPushToTalkChange: (v: boolean) => void;
}
