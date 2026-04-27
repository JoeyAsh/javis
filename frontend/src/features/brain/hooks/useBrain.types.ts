import type {
    DeviceEvent,
    VoiceComposerStatus,
    LedgerKind,
    LedgerKindCounts,
    LedgerQueryRequest,
} from '../types';

export interface UseBrainReturn {
    voiceComposerStatus: VoiceComposerStatus;
    filteredEvents: DeviceEvent[];
    counts24h: LedgerKindCounts;
    kindFilter: LedgerKind[];
    sinceFilter: number | null;
    setKinds: (kinds: LedgerKind[]) => void;
    setSince: (ms: number | null) => void;
    requestLedgerQuery: (request: LedgerQueryRequest) => void;
}
