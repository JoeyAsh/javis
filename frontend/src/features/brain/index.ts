// Public barrel — consumers import from '@features/brain', not from internal paths.
export { LedgerInspector } from './components/LedgerInspector';
export type { LedgerInspectorProps } from './components/LedgerInspector';
export { useBrain } from './hooks/useBrain';
export type { UseBrainReturn } from './hooks/useBrain.types';
export { brainApi, useStreamBrainInspectorQuery, sendLedgerQuery } from './brainApi';
export { brainInspectorReceived, setKindFilter, setSinceFilter } from './brainSlice';
export type { BrainState } from './brainSlice';
export {
    selectVoiceComposerStatus,
    selectLedgerRecent,
    selectCounts24h,
    selectKindFilter,
    selectSinceFilter,
} from './brainSelectors';
export type {
    LedgerKind,
    LedgerSource,
    DeviceEvent,
    VoiceComposerStatus,
    LedgerKindCounts,
    BrainInspectorPayload,
    LedgerQueryRequest,
} from './types';
