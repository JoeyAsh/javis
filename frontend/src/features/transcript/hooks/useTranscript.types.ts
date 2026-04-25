import type { TranscriptTurn } from '../types';

export interface UseTranscriptReturn {
    turns: TranscriptTurn[];
    hasLiveData: boolean;
}
