import { useEffect, useState } from 'react';
import type { ReactElement } from 'react';
import { Label, Mono } from '@ui';
import { Toggle } from '../Toggle';
import type { AudioSectionProps, MicPermission } from './AudioSection.types';

export function AudioSection({
    micDeviceId,
    onMicDeviceChange,
    pushToTalk,
    onPushToTalkChange,
}: AudioSectionProps): ReactElement {
    const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
    const [permissionState, setPermissionState] = useState<MicPermission>('unknown');

    useEffect(() => {
        async function enumerateDevices() {
            try {
                await navigator.mediaDevices.getUserMedia({ audio: true }).then((s) => {
                    s.getTracks().forEach((t) => t.stop());
                });
                const all = await navigator.mediaDevices.enumerateDevices();
                setDevices(all.filter((d) => d.kind === 'audioinput'));
                setPermissionState('granted');
            } catch {
                setPermissionState('denied');
            }
        }
        void enumerateDevices();
    }, []);

    return (
        <div className="border-b border-border pb-5 mb-5">
            <Label className="text-accent block mb-[14px] text-[10px] tracking-[0.15em] uppercase">
                Audio
            </Label>

            <div className="mb-[14px]">
                <Label htmlFor="sv-mic-select" className="block mb-1">
                    Mikrofon
                </Label>
                {permissionState === 'denied' ? (
                    <div className="bg-warning/10 border border-warning/30 rounded-[2px] px-2 py-1.5 mt-1">
                        <Mono size="sm">
                            Microphone permission denied. Allow access in browser settings and
                            reload.
                        </Mono>
                    </div>
                ) : (
                    <select
                        id="sv-mic-select"
                        value={micDeviceId}
                        onChange={(e) => onMicDeviceChange(e.target.value)}
                        className="w-full bg-black/35 border border-border rounded-[2px] text-text font-mono text-[12px] px-2 py-[5px] outline-none cursor-pointer mt-1"
                    >
                        <option value="">System default</option>
                        {devices.map((d) => (
                            <option key={d.deviceId} value={d.deviceId}>
                                {d.label || `Microphone ${d.deviceId.slice(0, 8)}`}
                            </option>
                        ))}
                    </select>
                )}
            </div>

            <Toggle
                checked={pushToTalk}
                onChange={onPushToTalkChange}
                label="Push-to-Talk"
                description="Hold the PTT button near the orb to record instead of using wake word."
            />
        </div>
    );
}

export default AudioSection;
