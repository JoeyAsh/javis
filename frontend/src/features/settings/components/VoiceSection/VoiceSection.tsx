import type { ReactElement } from 'react';
import { Label } from '@ui';
import { Toggle } from '../Toggle';
import type { VoiceSectionProps } from './VoiceSection.types';

export function VoiceSection({
    autoSpeakClaude,
    onAutoSpeakChange,
    heartbeatEnabled,
    onHeartbeatChange,
}: VoiceSectionProps): ReactElement {
    return (
        <div className="border-b border-border pb-5 mb-5">
            <Label className="text-accent block mb-[14px] text-[10px] tracking-[0.15em] uppercase">
                Voice
            </Label>
            <Toggle
                checked={autoSpeakClaude}
                onChange={onAutoSpeakChange}
                label="Nachrichten automatisch vorlesen"
                description="When OFF, TTS only plays for explicit voice turns."
            />
            <Toggle
                checked={heartbeatEnabled}
                onChange={onHeartbeatChange}
                label="Heartbeat idle sound"
                description="Plays a subtle heartbeat loop after 30 s of idling."
            />
        </div>
    );
}

export default VoiceSection;
