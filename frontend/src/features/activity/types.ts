/**
 * Activity feature types — NarrationItem, NarrationState, and WS payload shapes.
 */

/** Severity of a narration item — maps to colour-coded badges in the UI. */
export type NarrationSeverity = 'info' | 'update' | 'urgent' | 'completion';

/** Operational state emitted by the backend narration engine. */
export type NarrationEngineState = 'idle' | 'listening' | 'speaking' | 'active_dialogue';

/** Per-source activity status emitted by the backend. */
export type SourceStatus = 'starting' | 'in_progress' | 'done' | 'blocked';

/** A single item in the narration queue / history — mirrors the backend dataclass. */
export interface NarrationItem {
    id: string;
    text: string;
    severity: NarrationSeverity;
    source: string | null;
    /** ISO 8601 timestamp. */
    created_at: string;
    /** Optional TTL in seconds. */
    ttl_seconds: number | null;
}

/** Per-source status row emitted in the activity_panel payload. */
export interface SourceEntry {
    status: SourceStatus;
    message: string;
    /** ISO 8601 timestamp of the last status update. */
    updated_at: string;
}

/** WS payload for `narration_state` message type. */
export interface NarrationStatePayload {
    state: NarrationEngineState;
    /** ISO 8601 or null when quiet mode is off. */
    quiet_until: string | null;
    items: NarrationItem[];
}

/** WS payload for `activity_panel` message type. */
export interface ActivityPanelPayload {
    sources: Record<string, SourceEntry>;
    history: NarrationItem[];
}
