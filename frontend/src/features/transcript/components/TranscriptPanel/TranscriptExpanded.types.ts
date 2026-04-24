import type { TranscriptTurn } from '../../types';
import type { TranscriptPanelProps } from './TranscriptPanel.types';

export interface TranscriptExpandedProps {
    turns: TranscriptTurn[];
    orbState: NonNullable<TranscriptPanelProps['orbState']>;
}
