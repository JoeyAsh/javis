import type { SectionId } from '../../types';

export interface SettingsNavProps {
    activeSection: SectionId;
    onSelect: (id: SectionId) => void;
}
