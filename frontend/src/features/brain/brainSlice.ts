import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import type {
    DeviceEvent,
    VoiceComposerStatus,
    LedgerKind,
    LedgerKindCounts,
    BrainInspectorPayload,
} from './types';

const MAX_RECENT = 50;

export interface BrainState {
    voiceComposerStatus: VoiceComposerStatus;
    /** Last 50 events, dedup-by-id, newest first. */
    recent: DeviceEvent[];
    counts24h: LedgerKindCounts;
    filter: {
        kinds: LedgerKind[];
        /** `Date.now() - lookbackMs` cutoff, or null for all time. */
        sinceMs: number | null;
    };
    lastInspectorTs: string | null;
}

const initialState: BrainState = {
    voiceComposerStatus: {
        last_compose_ts: null,
        last_salutation: null,
    },
    recent: [],
    counts24h: {},
    filter: {
        kinds: [],
        sinceMs: null,
    },
    lastInspectorTs: null,
};

/**
 * Merge incoming events into existing, dedup by id, sort desc by ts, keep max MAX_RECENT.
 */
function mergeEvents(existing: DeviceEvent[], incoming: DeviceEvent[]): DeviceEvent[] {
    const byId = new Map<number, DeviceEvent>(existing.map((e) => [e.id, e]));
    for (const ev of incoming) {
        byId.set(ev.id, ev);
    }
    const merged = Array.from(byId.values());
    merged.sort((a, b) => b.ts.localeCompare(a.ts));
    return merged.length > MAX_RECENT ? merged.slice(0, MAX_RECENT) : merged;
}

const brainSlice = createSlice({
    name: 'brain',
    initialState,
    reducers: {
        brainInspectorReceived(state, action: PayloadAction<BrainInspectorPayload>) {
            state.voiceComposerStatus = action.payload.voice_composer_status;
            state.counts24h = action.payload.ledger_count_24h;
            state.recent = mergeEvents(state.recent as DeviceEvent[], action.payload.ledger_recent);
            state.lastInspectorTs = new Date().toISOString();
        },
        setKindFilter(state, action: PayloadAction<LedgerKind[]>) {
            state.filter.kinds = action.payload;
        },
        setSinceFilter(state, action: PayloadAction<number | null>) {
            state.filter.sinceMs = action.payload;
        },
    },
});

export const { brainInspectorReceived, setKindFilter, setSinceFilter } = brainSlice.actions;
export default brainSlice.reducer;
