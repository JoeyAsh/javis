import type { TranscriptTurn } from '../../types';
import type { AppOrbState, PanelMode } from '../../../../types';

export interface TranscriptPanelProps {
    /** Optional prop override for tests / storybook. */
    turns?: TranscriptTurn[];
    mode?: PanelMode;
    orbState?: AppOrbState;
}
