/**
 * SettingsOverlay — full-screen modal with HUD polish settings.
 *
 * Sections:
 *   Audio    — microphone device select, push-to-talk toggle
 *   Display  — panel opacity slider
 *   Voice    — auto-speak Claude messages toggle
 *   Repositories — GitHub + GitLab repo path management (reads/POSTs /api/config/repos)
 *   Persona  — read-only owner + salutation note
 *
 * Opens via gear icon in TopBar; closes on Escape or backdrop click.
 * z-index 50 — above panels (10), top bar (30), dev menu (40).
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import type { ReactElement } from 'react';
import type { UseSettingsReturn, OrbVariant } from '../hooks/useSettings';
import { useSfx } from '../hud/SfxContext';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ReposConfig {
  github: string[];
  gitlab: string[];
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SECTION_STYLE: React.CSSProperties = {
  borderBottom: '1px solid var(--border)',
  paddingBottom: 20,
  marginBottom: 20,
};

const LABEL_STYLE: React.CSSProperties = {
  display: 'block',
  fontSize: 9,
  letterSpacing: '0.15em',
  textTransform: 'uppercase',
  color: 'var(--text-muted)',
  marginBottom: 6,
  fontFamily: 'var(--font)',
};

const INPUT_STYLE: React.CSSProperties = {
  width: '100%',
  background: 'rgba(0,0,0,0.35)',
  border: '1px solid var(--border)',
  borderRadius: 2,
  color: 'var(--text)',
  fontFamily: 'var(--font)',
  fontSize: 12,
  padding: '5px 8px',
  outline: 'none',
};

const ROW_STYLE: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: 12,
  marginBottom: 14,
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

interface ToggleProps {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  description?: string;
}

function Toggle({ checked, onChange, label, description }: ToggleProps): ReactElement {
  return (
    <div style={ROW_STYLE}>
      <div>
        <div
          style={{ fontSize: 12, color: 'var(--text)', fontFamily: 'var(--font)', marginBottom: 2 }}
        >
          {label}
        </div>
        {description && (
          <div
            style={{
              fontSize: 10,
              color: 'var(--text-secondary)',
              fontFamily: 'var(--font)',
              lineHeight: 1.4,
            }}
          >
            {description}
          </div>
        )}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => { onChange(!checked); }}
        style={{
          flexShrink: 0,
          width: 36,
          height: 18,
          borderRadius: 2,
          border: `1px solid ${checked ? 'var(--accent)' : 'var(--border)'}`,
          background: checked ? 'rgba(76,168,232,0.25)' : 'rgba(0,0,0,0.3)',
          cursor: 'pointer',
          position: 'relative',
          transition: 'background 180ms, border-color 180ms',
        }}
      >
        <span
          style={{
            position: 'absolute',
            top: 2,
            left: checked ? 18 : 2,
            width: 12,
            height: 12,
            borderRadius: 1,
            background: checked ? 'var(--accent)' : 'var(--text-muted)',
            transition: 'left 160ms, background 160ms',
          }}
        />
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// AudioSection
// ---------------------------------------------------------------------------

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
        // Request mic permission so labels are populated.
        await navigator.mediaDevices.getUserMedia({ audio: true }).then((s) => {
          s.getTracks().forEach((t) => { t.stop(); });
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
    <div style={SECTION_STYLE}>
      <div
        style={{
          fontSize: 10,
          letterSpacing: '0.15em',
          textTransform: 'uppercase',
          color: 'var(--accent)',
          fontFamily: 'var(--font)',
          marginBottom: 14,
        }}
      >
        Audio
      </div>

      <div style={{ marginBottom: 14 }}>
        <label style={LABEL_STYLE} htmlFor="settings-mic-select">
          Mikrofon
        </label>
        {permissionState === 'denied' ? (
          <div
            style={{
              fontSize: 11,
              color: 'var(--warning)',
              fontFamily: 'var(--font)',
              background: 'rgba(232,168,76,0.1)',
              border: '1px solid rgba(232,168,76,0.3)',
              borderRadius: 2,
              padding: '6px 8px',
            }}
          >
            Microphone permission denied. Allow access in browser settings and reload.
          </div>
        ) : (
          <select
            id="settings-mic-select"
            value={micDeviceId}
            onChange={(e) => { onMicDeviceChange(e.target.value); }}
            style={{ ...INPUT_STYLE, cursor: 'pointer' }}
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

// ---------------------------------------------------------------------------
// DisplaySection
// ---------------------------------------------------------------------------

interface DisplaySectionProps {
  panelOpacity: number;
  onPanelOpacityChange: (v: number) => void;
  orbVariant: OrbVariant;
  onOrbVariantChange: (v: OrbVariant) => void;
}

function DisplaySection({ panelOpacity, onPanelOpacityChange, orbVariant, onOrbVariantChange }: DisplaySectionProps): ReactElement {
  return (
    <div style={SECTION_STYLE}>
      <div
        style={{
          fontSize: 10,
          letterSpacing: '0.15em',
          textTransform: 'uppercase',
          color: 'var(--accent)',
          fontFamily: 'var(--font)',
          marginBottom: 14,
        }}
      >
        Display
      </div>

      <label style={LABEL_STYLE} htmlFor="settings-opacity-slider">
        Panel opacity — {Math.round(panelOpacity * 100)}%
      </label>
      <input
        id="settings-opacity-slider"
        type="range"
        min={0.5}
        max={1.0}
        step={0.01}
        value={panelOpacity}
        onChange={(e) => { onPanelOpacityChange(parseFloat(e.target.value)); }}
        style={{ width: '100%', accentColor: 'var(--accent)', cursor: 'pointer' }}
      />

      <label style={{ ...LABEL_STYLE, marginTop: 16 }} htmlFor="settings-orb-variant">
        Orb Style
      </label>
      <select
        id="settings-orb-variant"
        value={orbVariant}
        onChange={(e) => { onOrbVariantChange(e.target.value as OrbVariant); }}
        style={{ ...INPUT_STYLE, cursor: 'pointer' }}
      >
        <option value="classic">Classic (Three.js)</option>
        <option value="hypermodern">Hypermodern (CSS)</option>
      </select>
    </div>
  );
}

// ---------------------------------------------------------------------------
// VoiceSection
// ---------------------------------------------------------------------------

interface VoiceSectionProps {
  autoSpeakClaude: boolean;
  onAutoSpeakChange: (v: boolean) => void;
  heartbeatEnabled: boolean;
  onHeartbeatChange: (v: boolean) => void;
}

function VoiceSection({ autoSpeakClaude, onAutoSpeakChange, heartbeatEnabled, onHeartbeatChange }: VoiceSectionProps): ReactElement {
  return (
    <div style={SECTION_STYLE}>
      <div
        style={{
          fontSize: 10,
          letterSpacing: '0.15em',
          textTransform: 'uppercase',
          color: 'var(--accent)',
          fontFamily: 'var(--font)',
          marginBottom: 14,
        }}
      >
        Voice
      </div>

      <Toggle
        checked={autoSpeakClaude}
        onChange={onAutoSpeakChange}
        label="Nachrichten automatisch vorlesen"
        description="When OFF, TTS only plays for explicit voice turns. Claude-initiated notifications stay silent."
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

// ---------------------------------------------------------------------------
// RepositoriesSection
// ---------------------------------------------------------------------------

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
    <div style={{ marginBottom: 14 }}>
      <label style={LABEL_STYLE}>{label}</label>
      <div
        style={{
          border: '1px solid var(--border)',
          borderRadius: 2,
          background: 'rgba(0,0,0,0.2)',
          padding: '6px 8px',
          minHeight: 40,
          marginBottom: 6,
        }}
      >
        {repos.length === 0 && (
          <span
            style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font)' }}
          >
            No repositories configured.
          </span>
        )}
        {repos.map((r) => (
          <div
            key={r}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '2px 0',
            }}
          >
            <span
              style={{ fontSize: 11, color: 'var(--text-secondary)', fontFamily: 'var(--font)' }}
            >
              {r}
            </span>
            {!readonly && (
              <button
                type="button"
                onClick={() => { onRemove(r); }}
                aria-label={`Remove ${r}`}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                  fontFamily: 'var(--font)',
                  fontSize: 11,
                  padding: '0 4px',
                  transition: 'color 150ms',
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLButtonElement).style.color = 'var(--danger)';
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-muted)';
                }}
              >
                ×
              </button>
            )}
          </div>
        ))}
      </div>
      {!readonly && (
        <div style={{ display: 'flex', gap: 6 }}>
          <input
            type="text"
            placeholder="owner/repo"
            value={inputValue}
            onChange={(e) => { setInputValue(e.target.value); }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleAdd();
            }}
            style={{ ...INPUT_STYLE, flex: 1 }}
          />
          <button
            type="button"
            onClick={handleAdd}
            style={{
              background: 'rgba(76,168,232,0.15)',
              border: '1px solid var(--accent)',
              borderRadius: 2,
              color: 'var(--accent)',
              cursor: 'pointer',
              fontFamily: 'var(--font)',
              fontSize: 11,
              padding: '4px 10px',
              transition: 'background 150ms',
            }}
          >
            ADD
          </button>
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
        if (!res.ok) throw new Error('Non-2xx response');
        const data = (await res.json()) as ReposConfig;
        setRepos(data);
      } catch {
        // Backend unavailable — show read-only placeholder
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
      setTimeout(() => { setSaveStatus('idle'); }, 1500);
    } catch {
      setSaveStatus('error');
      setTimeout(() => { setSaveStatus('idle'); }, 2000);
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
    <div style={SECTION_STYLE}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 14,
        }}
      >
        <div
          style={{
            fontSize: 10,
            letterSpacing: '0.15em',
            textTransform: 'uppercase',
            color: 'var(--accent)',
            fontFamily: 'var(--font)',
          }}
        >
          Repositories
        </div>
        {saveStatus === 'saving' && (
          <span style={{ fontSize: 9, color: 'var(--text-muted)', fontFamily: 'var(--font)' }}>
            saving...
          </span>
        )}
        {saveStatus === 'saved' && (
          <span style={{ fontSize: 9, color: 'var(--success)', fontFamily: 'var(--font)' }}>
            saved
          </span>
        )}
        {saveStatus === 'error' && (
          <span style={{ fontSize: 9, color: 'var(--danger)', fontFamily: 'var(--font)' }}>
            save failed
          </span>
        )}
      </div>

      {readOnly && (
        <div
          style={{
            fontSize: 10,
            color: 'var(--warning)',
            fontFamily: 'var(--font)',
            marginBottom: 10,
            background: 'rgba(232,168,76,0.08)',
            border: '1px solid rgba(232,168,76,0.25)',
            borderRadius: 2,
            padding: '4px 8px',
          }}
        >
          Backend unavailable — displaying read-only.
        </div>
      )}

      {loading ? (
        <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font)' }}>
          Loading...
        </div>
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

// ---------------------------------------------------------------------------
// PersonaSection
// ---------------------------------------------------------------------------

function PersonaSection(): ReactElement {
  return (
    <div style={{ paddingBottom: 4 }}>
      <div
        style={{
          fontSize: 10,
          letterSpacing: '0.15em',
          textTransform: 'uppercase',
          color: 'var(--accent)',
          fontFamily: 'var(--font)',
          marginBottom: 14,
        }}
      >
        Persona
      </div>

      <div
        style={{
          background: 'rgba(0,0,0,0.2)',
          border: '1px solid var(--border)',
          borderRadius: 2,
          padding: '8px 10px',
          fontFamily: 'var(--font)',
        }}
      >
        <div
          style={{
            fontSize: 11,
            color: 'var(--text-secondary)',
            marginBottom: 6,
            lineHeight: 1.5,
          }}
        >
          JARVIS belongs to:{' '}
          <span style={{ color: 'var(--accent)' }}>Johannes Aschenbrenner</span>
        </div>
        <div style={{ fontSize: 10, color: 'var(--text-muted)', lineHeight: 1.5 }}>
          Salutation mode: random (Sir / Johannes)
        </div>
        <div style={{ fontSize: 10, color: 'var(--text-muted)', lineHeight: 1.5, marginTop: 4 }}>
          Style: JARVIS — British formal. The Iron Man aesthetic is flavour only; the
          assistant serves the actual owner by name.
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// SettingsOverlay props + main component
// ---------------------------------------------------------------------------

export interface SettingsOverlayProps {
  open: boolean;
  onClose: () => void;
  settingsHook: UseSettingsReturn;
}

type SectionId = 'audio' | 'display' | 'voice' | 'repositories' | 'persona';

const SECTIONS: Array<{ id: SectionId; label: string }> = [
  { id: 'audio', label: 'Audio' },
  { id: 'display', label: 'Display' },
  { id: 'voice', label: 'Voice' },
  { id: 'repositories', label: 'Repositories' },
  { id: 'persona', label: 'Persona' },
];

export function SettingsOverlay({ open, onClose, settingsHook }: SettingsOverlayProps): ReactElement | null {
  const [activeSection, setActiveSection] = useState<SectionId>('audio');
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const { playOneShot } = useSfx();

  const { settings, setPanelOpacity, setAutoSpeakClaude, setPushToTalk, setMicDeviceId, setOrbVariant, setHeartbeatEnabled } =
    settingsHook;

  // Play menu_open on mount (when open becomes true) and menu_close on unmount.
  useEffect(() => {
    if (!open) return;
    playOneShot('menu_open');
    return () => {
      playOneShot('menu_close');
    };
  }, [open, playOneShot]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => { window.removeEventListener('keydown', onKey); };
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
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 50,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(5,5,8,0.7)',
        backdropFilter: 'blur(6px)',
        WebkitBackdropFilter: 'blur(6px)',
      }}
    >
      <div
        ref={dialogRef}
        style={{
          width: 640,
          maxWidth: 'calc(100vw - 40px)',
          maxHeight: 'calc(100vh - 80px)',
          background: 'rgba(13,13,20,0.95)',
          border: '1px solid var(--border)',
          borderRadius: 4,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          boxShadow: 'var(--glow-strong)',
        }}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '10px 16px',
            borderBottom: '1px solid var(--border)',
            background: 'rgba(0,0,0,0.2)',
          }}
        >
          <span
            style={{
              fontFamily: 'var(--font)',
              fontSize: 10,
              letterSpacing: '0.2em',
              textTransform: 'uppercase',
              color: 'var(--text-secondary)',
            }}
          >
            Settings
          </span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close settings"
            style={{
              background: 'transparent',
              border: '1px solid transparent',
              borderRadius: 2,
              color: 'var(--text-muted)',
              cursor: 'pointer',
              fontFamily: 'var(--font)',
              fontSize: 16,
              lineHeight: 1,
              padding: '2px 6px',
              transition: 'color 150ms, border-color 150ms',
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.color = 'var(--accent-bright)';
              (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--border)';
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-muted)';
              (e.currentTarget as HTMLButtonElement).style.borderColor = 'transparent';
            }}
          >
            ×
          </button>
        </div>

        {/* Body — sidebar nav + content */}
        <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
          {/* Sidebar nav */}
          <nav
            style={{
              width: 140,
              flexShrink: 0,
              borderRight: '1px solid var(--border)',
              padding: '12px 0',
              background: 'rgba(0,0,0,0.15)',
            }}
          >
            {SECTIONS.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => { setActiveSection(s.id); }}
                style={{
                  display: 'block',
                  width: '100%',
                  textAlign: 'left',
                  background: activeSection === s.id ? 'rgba(76,168,232,0.1)' : 'transparent',
                  border: 'none',
                  borderLeft: `2px solid ${activeSection === s.id ? 'var(--accent)' : 'transparent'}`,
                  color: activeSection === s.id ? 'var(--accent)' : 'var(--text-secondary)',
                  cursor: 'pointer',
                  fontFamily: 'var(--font)',
                  fontSize: 11,
                  letterSpacing: '0.08em',
                  padding: '8px 14px',
                  transition: 'color 150ms, background 150ms',
                }}
              >
                {s.label}
              </button>
            ))}
          </nav>

          {/* Content pane */}
          <div
            style={{
              flex: 1,
              overflowY: 'auto',
              padding: '20px 24px',
            }}
          >
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
                orbVariant={settings.orbVariant}
                onOrbVariantChange={setOrbVariant}
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
      </div>
    </div>
  );
}

export default SettingsOverlay;
