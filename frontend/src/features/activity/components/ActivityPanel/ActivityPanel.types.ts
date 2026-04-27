import type { PanelMode } from '@common/types';
import type { NarrationItem, SourceEntry } from '../../types';

export interface ActivityPanelProps {
    mode?: PanelMode;
}

export interface ActivitySourceListProps {
    sources: Record<string, SourceEntry>;
}

export interface ActivityHistoryListProps {
    history: NarrationItem[];
}

export interface ActivityQuietBarProps {
    quietUntil: string;
}
