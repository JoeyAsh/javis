// ── Main component ────────────────────────────────────────────────────────────
export { SettingsView } from './components/SettingsView';
export type { SettingsViewProps } from './components/SettingsView';

// ── Section components ────────────────────────────────────────────────────────
export { AudioSection } from './components/AudioSection';
export type { AudioSectionProps } from './components/AudioSection';

export { DisplaySection } from './components/DisplaySection';
export type { DisplaySectionProps } from './components/DisplaySection';

export { VoiceSection } from './components/VoiceSection';
export type { VoiceSectionProps } from './components/VoiceSection';

export { RepositoriesSection } from './components/RepositoriesSection';
export type { RepositoriesSectionProps } from './components/RepositoriesSection';

export { PersonaSection } from './components/PersonaSection';
export type { PersonaSectionProps } from './components/PersonaSection';

// ── Shared sub-components ─────────────────────────────────────────────────────
export { Toggle } from './components/Toggle';
export type { ToggleProps } from './components/Toggle';

export { SettingsNav } from './components/SettingsNav';
export type { SettingsNavProps } from './components/SettingsNav';

export { SettingsRow } from './components/SettingsRow';
export type { SettingsRowProps } from './components/SettingsRow';

// ── Hook ──────────────────────────────────────────────────────────────────────
export { useSettings } from './hooks/useSettings';
export type { UseSettingsReturn } from './hooks/useSettings.types';

// ── RTK Query api ─────────────────────────────────────────────────────────────
export { settingsApi, useGetReposQuery, useSaveReposMutation } from './settingsApi';

// ── Types ─────────────────────────────────────────────────────────────────────
export type { JarvisSettings, OrbStyle, ReposConfig, SectionId, SaveStatus } from './types';
