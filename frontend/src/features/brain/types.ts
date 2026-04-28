/**
 * Brain feature types — DeviceEvent, VoiceComposerStatus, and WS payload shapes.
 * Matches the backend WS contract verbatim.
 */

export type LedgerKind =
    | 'tts_emitted'
    | 'mcp_call'
    | 'wake_word'
    | 'orb_state'
    | 'panel_open'
    | 'panel_close'
    | 'barge_in'
    | 'voice_turn_start'
    | 'voice_turn_end'
    | 'error';

export type LedgerSource = 'voice' | 'hud' | 'scheduler' | 'system';

export interface DeviceEvent {
    id: number;
    correlation_id: string | null;
    kind: LedgerKind;
    source: LedgerSource;
    /** ISO 8601 timestamp. */
    ts: string;
    /** Already-parsed JSON payload. */
    payload: Record<string, unknown>;
}

export interface VoiceComposerStatus {
    last_compose_ts: string | null;
    last_salutation: string | null;
}

export type LedgerKindCounts = Partial<Record<LedgerKind, number>>;

export interface LedgerQueryRequest {
    /** ISO 8601. */
    since: string;
    until: string | null;
    /** Empty array means all kinds. */
    kinds: LedgerKind[];
}

export interface BrainInspectorPayload {
    voice_composer_status: VoiceComposerStatus;
    /** Last 10 events from backend. */
    ledger_recent: DeviceEvent[];
    ledger_count_24h: LedgerKindCounts;
}
