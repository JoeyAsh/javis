import { useAppSelector } from '@app';
import { useStreamTranscriptQuery } from '../transcriptApi';
import { selectTranscriptTurns, selectTranscriptHasLiveData } from '../transcriptSelectors';
import type { UseTranscriptReturn } from './useTranscript.types';

export function useTranscript(): UseTranscriptReturn {
    useStreamTranscriptQuery();

    const turns = useAppSelector(selectTranscriptTurns);
    const hasLiveData = useAppSelector(selectTranscriptHasLiveData);

    return { turns, hasLiveData };
}
