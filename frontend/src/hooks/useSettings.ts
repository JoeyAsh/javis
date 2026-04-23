/**
 * @deprecated — import from '@features/settings' instead.
 *
 * This shim re-exports everything from the canonical feature location so
 * existing imports from 'src/hooks/useSettings' continue to resolve.
 * It will be removed once all consumers have been migrated.
 */
export { useSettings, useSettings as default } from '../features/settings/hooks/useSettings';
export type { UseSettingsReturn } from '../features/settings/hooks/useSettings.types';
export type { JarvisSettings, OrbStyle } from '../features/settings/types';
