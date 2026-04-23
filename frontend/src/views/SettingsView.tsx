/**
 * SettingsView — full-screen modal settings overlay using lib primitives.
 *
 * Replaces legacy components/SettingsOverlay.tsx.
 * Uses lib GlassCard, Button, Label, Mono for display.
 *
 * Sections: Audio, Display, Voice, Repositories, Persona.
 * Opens via gear icon; closes on Escape or backdrop click.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import type { ReactElement } from 'react';
import { Button, GlassCard, Label, Mono } from '../lib';
import { useSfx } from '@core/audio';
import type { UseSettingsReturn, OrbStyle } from '../hooks/useSettings';
import './SettingsView.css';

// ── Types ────────────────────────────────────────────────────────────────────

interface ReposConfig {
    github: string[];
    gitlab: string[];
}

export interface SettingsViewProps {
    open: boolean;
    onClose: () => void;
    settingsHook: UseSettingsReturn;
}

type SectionId = 'audio' | 'display' | 'voice' | 'repositories' | 'persona';

const SECTIONS: ReadonlyArray<{ id: SectionId; label: string }> = [
    { id: 'audio', label: 'Audio' },
    { id: 'display', label: 'Display' },
    { id: 'voice', label: 'Voice' },
    { id: 'repositories', label: 'Repositories' },
    { id: 'persona', label: 'Persona' },
];

// ── Toggle sub-component ─────────────────────────────────────────────────────

interface ToggleProps {
    checked: boolean;
    onChange: (v: boolean) => void;
    label: string;
    description?: string;
}

function Toggle({ checked, onChange, label, description }: ToggleProps): ReactElement {
    return (
        <div className="sv-row">
            <div>
                <Mono size="md">{label}</Mono>
                {description && (
                    <Mono size="xs" secondary className="sv-desc">{description}</Mono>
                )}
            </div>
            <button
                type="button"
                role="switch"
                aria-checked={checked}
                onClick={() => onChange(!checked)}
                className={`sv-toggle ${checked ? 'sv-toggle--on' : ''}`}
            >
                <span className="sv-toggle__knob" />
            </button>
        </div>
    );
}

// ── Section header ───────────────────────────────────────────────────────────

function SectionTitle({ children }: { children: string }): ReactElement {
    return <Label className="sv-section-title">{children}</Label>;
}

// ── Audio section ────────────────────────────────────────────────────────────

interface AudioSectionProps {
    micDeviceId: string;
    onMicDeviceChange: (id: string) => void;
    pushToTalk: boolean;
    onPushToTalkChange: (v: boolean) => void;
}

function AudioSection({
    micDeviceId,
    onMicDeviceChange,
    pushToTalk,
    onPushToTalkChange,
}: AudioSectionProps): ReactElement {
    const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
    const [permissionState, setPermissionState] = useState<'unknown' | 'granted' | 'denied'>(
        'unknown',
    );

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
        <div className="sv-section">
            <SectionTitle>Audio</SectionTitle>

            <div className="sv-field">
                <Label htmlFor="sv-mic-select">Mikrofon</Label>
                {permissionState === 'denied' ? (
                    <div className="sv-warning">
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
                        className="sv-select"
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

// ── Display section ──────────────────────────────────────────────────────────

interface DisplaySectionProps {
    panelOpacity: number;
    onPanelOpacityChange: (v: number) => void;
    orbStyle: OrbStyle;
    onOrbStyleChange: (v: OrbStyle) => void;
}

function DisplaySection({
    panelOpacity,
    onPanelOpacityChange,
    orbStyle,
    onOrbStyleChange,
}: DisplaySectionProps): ReactElement {
    return (
        <div className="sv-section">
            <SectionTitle>Display</SectionTitle>
            <Label htmlFor="sv-opacity-slider">
                Panel opacity — {Math.round(panelOpacity * 100)}%
            </Label>
            <input
                id="sv-opacity-slider"
                type="range"
                min={0.5}
                max={1.0}
                step={0.01}
                value={panelOpacity}
                onChange={(e) => onPanelOpacityChange(parseFloat(e.target.value))}
                className="sv-slider"
            />

            <div className="sv-field" style={{ marginTop: 14 }}>
                <Label>Orb Style</Label>
                <div className="sv-orb-switcher">
                    <button
                        type="button"
                        className={`sv-orb-option ${orbStyle === 'css' ? 'sv-orb-option--active' : ''}`}
                        onClick={() => onOrbStyleChange('css')}
                    >
                        <Mono size="sm">CSS / DOM</Mono>
                        <Mono size="xs" muted>Rings, pulses, particles — lightweight</Mono>
                    </button>
                    <button
                        type="button"
                        className={`sv-orb-option ${orbStyle === 'threejs' ? 'sv-orb-option--active' : ''}`}
                        onClick={() => onOrbStyleChange('threejs')}
                    >
                        <Mono size="sm">Three.js</Mono>
                        <Mono size="xs" muted>2000 particles, WebGL — GPU-intensive</Mono>
                    </button>
                </div>
            </div>
        </div>
    );
}

// ── Voice section ────────────────────────────────────────────────────────────

interface VoiceSectionProps {
    autoSpeakClaude: boolean;
    onAutoSpeakChange: (v: boolean) => void;
    heartbeatEnabled: boolean;
    onHeartbeatChange: (v: boolean) => void;
}

function VoiceSection({
    autoSpeakClaude,
    onAutoSpeakChange,
    heartbeatEnabled,
    onHeartbeatChange,
}: VoiceSectionProps): ReactElement {
    return (
        <div className="sv-section">
            <SectionTitle>Voice</SectionTitle>
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

// ── Repositories section ─────────────────────────────────────────────────────

interface RepoListProps {
    label: string;
    repos: string[];
    onAdd: (repo: string) => void;
    onRemove: (repo: string) => void;
    readonly?: boolean;
}

function RepoList({ label, repos, onAdd, onRemove, readonly = false }: RepoListProps): ReactElement {
    const [inputValue, setInputValue] = useState('');

    function handleAdd() {
        const trimmed = inputValue.trim();
        if (trimmed && !repos.includes(trimmed)) {
            onAdd(trimmed);
            setInputValue('');
        }
    }

    return (
        <div className="sv-field">
            <Label>{label}</Label>
            <div className="sv-repo-list">
                {repos.length === 0 && (
                    <Mono size="sm" muted>No repositories configured.</Mono>
                )}
                {repos.map((r) => (
                    <div key={r} className="sv-repo-item">
                        <Mono size="sm" secondary>{r}</Mono>
                        {!readonly && (
                            <button
                                type="button"
                                onClick={() => onRemove(r)}
                                aria-label={`Remove ${r}`}
                                className="sv-repo-remove"
                            >
                                ×
                            </button>
                        )}
                    </div>
                ))}
            </div>
            {!readonly && (
                <div className="sv-repo-add">
                    <input
                        type="text"
                        placeholder="owner/repo"
                        value={inputValue}
                        onChange={(e) => setInputValue(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter') handleAdd(); }}
                        className="sv-input"
                    />
                    <Button variant="ghost" size="sm" onClick={handleAdd}>ADD</Button>
                </div>
            )}
        </div>
    );
}

function RepositoriesSection(): ReactElement {
    const [repos, setRepos] = useState<ReposConfig>({ github: [], gitlab: [] });
    const [loading, setLoading] = useState(true);
    const [readOnly, setReadOnly] = useState(false);
    const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');

    useEffect(() => {
        async function fetchRepos() {
            try {
                const res = await fetch('http://localhost:8766/api/config/repos');
                if (!res.ok) throw new Error('Non-2xx');
                const data = (await res.json()) as ReposConfig;
                setRepos(data);
            } catch {
                setReadOnly(true);
            } finally {
                setLoading(false);
            }
        }
        void fetchRepos();
    }, []);

    async function saveRepos(updated: ReposConfig) {
        setSaveStatus('saving');
        try {
            const res = await fetch('http://localhost:8766/api/config/repos', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(updated),
            });
            if (!res.ok) throw new Error('Save failed');
            setSaveStatus('saved');
            setTimeout(() => setSaveStatus('idle'), 1500);
        } catch {
            setSaveStatus('error');
            setTimeout(() => setSaveStatus('idle'), 2000);
        }
    }

    function addGithub(repo: string) {
        const updated = { ...repos, github: [...repos.github, repo] };
        setRepos(updated);
        void saveRepos(updated);
    }
    function removeGithub(repo: string) {
        const updated = { ...repos, github: repos.github.filter((r) => r !== repo) };
        setRepos(updated);
        void saveRepos(updated);
    }
    function addGitlab(repo: string) {
        const updated = { ...repos, gitlab: [...repos.gitlab, repo] };
        setRepos(updated);
        void saveRepos(updated);
    }
    function removeGitlab(repo: string) {
        const updated = { ...repos, gitlab: repos.gitlab.filter((r) => r !== repo) };
        setRepos(updated);
        void saveRepos(updated);
    }

    return (
        <div className="sv-section">
            <div className="sv-section-hdr">
                <SectionTitle>Repositories</SectionTitle>
                {saveStatus === 'saving' && <Mono size="xs" muted>saving...</Mono>}
                {saveStatus === 'saved' && (
                    <Mono size="xs" className="text-success">saved</Mono>
                )}
                {saveStatus === 'error' && (
                    <Mono size="xs" className="text-error">save failed</Mono>
                )}
            </div>

            {readOnly && (
                <div className="sv-warning">
                    <Mono size="sm">Backend unavailable — displaying read-only.</Mono>
                </div>
            )}

            {loading ? (
                <Mono size="sm" muted>Loading...</Mono>
            ) : (
                <>
                    <RepoList
                        label="GitHub"
                        repos={repos.github}
                        onAdd={addGithub}
                        onRemove={removeGithub}
                        readonly={readOnly}
                    />
                    <RepoList
                        label="GitLab"
                        repos={repos.gitlab}
                        onAdd={addGitlab}
                        onRemove={removeGitlab}
                        readonly={readOnly}
                    />
                </>
            )}
        </div>
    );
}

// ── Persona section ──────────────────────────────────────────────────────────

function PersonaSection(): ReactElement {
    return (
        <div className="sv-section sv-section--last">
            <SectionTitle>Persona</SectionTitle>
            <div className="sv-persona-card">
                <Mono size="sm" secondary>
                    JARVIS belongs to:{' '}
                    <span className="text-accent">Johannes Aschenbrenner</span>
                </Mono>
                <Mono size="xs" muted className="sv-persona-line">
                    Salutation mode: random (Sir / Johannes)
                </Mono>
                <Mono size="xs" muted className="sv-persona-line">
                    Style: JARVIS — British formal. The Iron Man aesthetic is flavour only.
                </Mono>
            </div>
        </div>
    );
}

// ── Main component ───────────────────────────────────────────────────────────

export function SettingsView({
    open,
    onClose,
    settingsHook,
}: SettingsViewProps): ReactElement | null {
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
            className="sv-backdrop"
        >
            <div ref={dialogRef} className="sv-dialog-wrapper">
            <GlassCard className="sv-dialog">
                {/* Header */}
                <div className="sv-header">
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
                <div className="sv-body">
                    {/* Sidebar nav */}
                    <nav className="sv-nav">
                        {SECTIONS.map((s) => (
                            <button
                                key={s.id}
                                type="button"
                                onClick={() => setActiveSection(s.id)}
                                className={`sv-nav__item ${activeSection === s.id ? 'sv-nav__item--active' : ''}`}
                            >
                                {s.label}
                            </button>
                        ))}
                    </nav>

                    {/* Content */}
                    <div className="sv-content">
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


