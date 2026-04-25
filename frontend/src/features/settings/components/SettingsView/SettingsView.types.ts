import type { UseSettingsReturn } from '../../hooks/useSettings.types';

export interface SettingsViewProps {
    open: boolean;
    onClose: () => void;
    settingsHook: UseSettingsReturn;
}
