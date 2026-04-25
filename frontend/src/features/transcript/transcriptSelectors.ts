import type { RootState } from '@app';
import type { TranscriptTurn } from './types';

export function selectTranscriptTurns(state: RootState): TranscriptTurn[] {
    return state.transcript.turns;
}

export function selectTranscriptHasLiveData(state: RootState): boolean {
    return state.transcript.hasLiveData;
}
