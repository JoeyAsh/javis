import type { PanelMode } from '@common/types';
import type { GitLabStatePayload } from '../../types';

export interface GitLabPanelProps {
    mode?: PanelMode;
}

export interface GitLabCompactProps {
    data: GitLabStatePayload | null;
}

export interface GitLabExpandedProps {
    data: GitLabStatePayload | null;
}
