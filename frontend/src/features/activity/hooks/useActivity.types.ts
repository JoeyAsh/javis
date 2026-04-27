import type { NarrationItem, NarrationEngineState, SourceEntry } from '../types';

export interface UseActivityReturn {
    engineState: NarrationEngineState;
    quietUntil: string | null;
    sources: Record<string, SourceEntry>;
    history: NarrationItem[];
    hasLiveData: boolean;
}
