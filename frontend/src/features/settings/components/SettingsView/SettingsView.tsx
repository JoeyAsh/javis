/**
 * SettingsView — full-screen modal settings overlay.
 *
 * Sections: Audio, Display, Voice, Repositories, Persona.
 * Opens via gear icon; closes on Escape or backdrop click.
 * z-index 50 — above panels (10), top bar (30), dev menu (40).
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import type { ReactElement } from 'react';
import { Button, GlassCard, Label } from '@ui';
import { useSfx } from '@core/audio';
import { SettingsNav } from '../SettingsNav';
import { AudioSection } from '../AudioSection';
import { DisplaySection } from '../DisplaySection';
import { VoiceSection } from '../VoiceSection';
import { RepositoriesSection } from '../RepositoriesSection';
import { PersonaSection } from '../PersonaSection';
import type { SectionId } from '../../types';
import type { SettingsViewProps } from './SettingsView.types';

export function SettingsView({ open, onClose, settingsHook }: SettingsViewProps): ReactElement | null {
    const [activeSection, setActiveSection] = useState<SectionId>('audio');
    const dialogRef = useRef<HTMLDivElement | null>(null);
    const { playOneShot } = useSfx();

    const {
        settings,
        setPanelOpacity,
        setAutoSpeakClaude,
        setPushToTalk,
        setMicDeviceId,
        setHeartbeatEnabled,
        setOrbStyle,
    } = settingsHook;

    useEffect(() => {
        if (!open) return;
        playOneShot('menu_open');
        return () => { playOneShot('menu_close'); };
    }, [open, playOneShot]);

    useEffect(() => {
        if (!open) return;
        const onKey = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [open, onClose]);

    const handleBackdropClick = useCallback(
        (e: React.MouseEvent<HTMLDivElement>) => {
            if (dialogRef.current && !dialogRef.current.contains(e.target as Node)) {
                onClose();
            }
        },
        [onClose],
    );

    if (!open) return null;

    return (
        <div
            role="dialog"
            aria-modal="true"
            aria-label="JARVIS Settings"
            onClick={handleBackdropClick}
            className="fixed inset-0 z-50 flex items-center justify-center bg-bg/70 backdrop-blur-[6px]"
        >
            <div
                ref={dialogRef}
                className="w-[640px] max-w-[calc(100vw-40px)] max-h-[calc(100vh-80px)] flex flex-col overflow-hidden"
            >
                <GlassCard className="w-full h-full flex flex-col overflow-hidden">
                    {/* Header */}
                    <div className="flex items-center justify-between px-4 py-[10px] border-b border-border bg-black/20">
                        <Label>Settings</Label>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={onClose}
                            aria-label="Close settings"
                        >
                            ×
                        </Button>
                    </div>

                    {/* Body */}
                    <div className="flex flex-1 overflow-hidden">
                        <SettingsNav
                            activeSection={activeSection}
                            onSelect={setActiveSection}
                        />

                        {/* Content */}
                        <div className="flex-1 overflow-y-auto px-6 py-5">
                            {activeSection === 'audio' && (
                                <AudioSection
                                    micDeviceId={settings.micDeviceId}
                                    onMicDeviceChange={setMicDeviceId}
                                    pushToTalk={settings.pushToTalk}
                                    onPushToTalkChange={setPushToTalk}
                                />
                            )}
                            {activeSection === 'display' && (
                                <DisplaySection
                                    panelOpacity={settings.panelOpacity}
                                    onPanelOpacityChange={setPanelOpacity}
                                    orbStyle={settings.orbStyle}
                                    onOrbStyleChange={setOrbStyle}
                                />
                            )}
                            {activeSection === 'voice' && (
                                <VoiceSection
                                    autoSpeakClaude={settings.autoSpeakClaude}
                                    onAutoSpeakChange={setAutoSpeakClaude}
                                    heartbeatEnabled={settings.heartbeatEnabled}
                                    onHeartbeatChange={setHeartbeatEnabled}
                                />
                            )}
                            {activeSection === 'repositories' && <RepositoriesSection />}
                            {activeSection === 'persona' && <PersonaSection />}
                        </div>
                    </div>
                </GlassCard>
            </div>
        </div>
    );
}

export default SettingsView;
