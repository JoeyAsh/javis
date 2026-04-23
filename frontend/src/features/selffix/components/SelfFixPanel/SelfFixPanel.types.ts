import type { PanelMode } from '../../../../types';
import type { SelfFixEntry } from '../../types';

export interface SelfFixPanelProps {
    entries?: SelfFixEntry[];
    mode?: PanelMode;
}

export interface SelfFixCompactInnerProps {
    entries: SelfFixEntry[];
}

export interface SelfFixExpandedInnerProps {
    entries: SelfFixEntry[];
}
