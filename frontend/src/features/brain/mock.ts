/**
 * Sample data for development, tests, and Storybook-style use.
 */
import type {
    DeviceEvent,
    VoiceComposerStatus,
    BrainInspectorPayload,
    LedgerKindCounts,
} from './types';
import type { BrainState } from './brainSlice';

const now = Date.now();
const ago = (ms: number): string => new Date(now - ms).toISOString();

const CORR_A = 'corr-aaaa-1111';
const CORR_B = 'corr-bbbb-2222';
const CORR_C = 'corr-cccc-3333';
const CORR_D = 'corr-dddd-4444';
const CORR_E = 'corr-eeee-5555';

export const MOCK_DEVICE_EVENTS: DeviceEvent[] = [
    { id: 1,  correlation_id: CORR_A, kind: 'wake_word',        source: 'voice',     ts: ago(600_000), payload: { model: 'jarvis' } },
    { id: 2,  correlation_id: CORR_A, kind: 'voice_turn_start', source: 'voice',     ts: ago(599_500), payload: {} },
    { id: 3,  correlation_id: CORR_A, kind: 'mcp_call',         source: 'voice',     ts: ago(598_000), payload: { tool: 'get_calendar', duration_ms: 120 } },
    { id: 4,  correlation_id: CORR_A, kind: 'tts_emitted',      source: 'voice',     ts: ago(596_000), payload: { char_count: 87, duration_ms: 2400, voice_id: 'fish-v1' } },
    { id: 5,  correlation_id: CORR_A, kind: 'orb_state',        source: 'voice',     ts: ago(595_000), payload: { state: 'speaking' } },
    { id: 6,  correlation_id: CORR_A, kind: 'voice_turn_end',   source: 'voice',     ts: ago(593_000), payload: {} },
    { id: 7,  correlation_id: CORR_A, kind: 'orb_state',        source: 'voice',     ts: ago(592_000), payload: { state: 'idle' } },

    { id: 8,  correlation_id: CORR_B, kind: 'panel_open',       source: 'hud',       ts: ago(500_000), payload: { panel: 'mail' } },
    { id: 9,  correlation_id: CORR_B, kind: 'panel_close',      source: 'hud',       ts: ago(490_000), payload: { panel: 'mail' } },

    { id: 10, correlation_id: CORR_C, kind: 'wake_word',        source: 'voice',     ts: ago(400_000), payload: { model: 'jarvis' } },
    { id: 11, correlation_id: CORR_C, kind: 'voice_turn_start', source: 'voice',     ts: ago(399_500), payload: {} },
    { id: 12, correlation_id: CORR_C, kind: 'tts_emitted',      source: 'voice',     ts: ago(397_000), payload: { char_count: 132, duration_ms: 3800, voice_id: 'fish-v1' } },
    { id: 13, correlation_id: CORR_C, kind: 'voice_turn_end',   source: 'voice',     ts: ago(395_000), payload: {} },

    { id: 14, correlation_id: null,   kind: 'orb_state',        source: 'system',    ts: ago(300_000), payload: { state: 'connecting' } },
    { id: 15, correlation_id: null,   kind: 'orb_state',        source: 'system',    ts: ago(299_000), payload: { state: 'idle' } },

    { id: 16, correlation_id: CORR_D, kind: 'wake_word',        source: 'voice',     ts: ago(200_000), payload: { model: 'jarvis' } },
    { id: 17, correlation_id: CORR_D, kind: 'voice_turn_start', source: 'voice',     ts: ago(199_500), payload: {} },
    { id: 18, correlation_id: CORR_D, kind: 'mcp_call',         source: 'voice',     ts: ago(198_000), payload: { tool: 'get_weather', duration_ms: 95 } },
    { id: 19, correlation_id: CORR_D, kind: 'mcp_call',         source: 'voice',     ts: ago(197_500), payload: { tool: 'get_news', duration_ms: 210 } },
    { id: 20, correlation_id: CORR_D, kind: 'tts_emitted',      source: 'voice',     ts: ago(196_000), payload: { char_count: 204, duration_ms: 5200, voice_id: 'fish-v1' } },
    { id: 21, correlation_id: CORR_D, kind: 'orb_state',        source: 'voice',     ts: ago(195_500), payload: { state: 'speaking' } },
    { id: 22, correlation_id: CORR_D, kind: 'voice_turn_end',   source: 'voice',     ts: ago(193_000), payload: {} },
    { id: 23, correlation_id: CORR_D, kind: 'orb_state',        source: 'voice',     ts: ago(192_000), payload: { state: 'idle' } },

    { id: 24, correlation_id: null,   kind: 'panel_open',       source: 'hud',       ts: ago(150_000), payload: { panel: 'agenda' } },
    { id: 25, correlation_id: null,   kind: 'panel_close',      source: 'hud',       ts: ago(140_000), payload: { panel: 'agenda' } },
    { id: 26, correlation_id: null,   kind: 'panel_open',       source: 'hud',       ts: ago(130_000), payload: { panel: 'gitlab' } },
    { id: 27, correlation_id: null,   kind: 'panel_close',      source: 'hud',       ts: ago(120_000), payload: { panel: 'gitlab' } },

    { id: 28, correlation_id: CORR_E, kind: 'wake_word',        source: 'voice',     ts: ago(90_000),  payload: { model: 'jarvis' } },
    { id: 29, correlation_id: CORR_E, kind: 'barge_in',         source: 'voice',     ts: ago(89_500),  payload: {} },
    { id: 30, correlation_id: CORR_E, kind: 'voice_turn_start', source: 'voice',     ts: ago(89_000),  payload: {} },
    { id: 31, correlation_id: CORR_E, kind: 'mcp_call',         source: 'voice',     ts: ago(88_000),  payload: { tool: 'get_calendar', duration_ms: 145 } },
    { id: 32, correlation_id: CORR_E, kind: 'tts_emitted',      source: 'voice',     ts: ago(86_500),  payload: { char_count: 58, duration_ms: 1600, voice_id: 'fish-v1' } },
    { id: 33, correlation_id: CORR_E, kind: 'voice_turn_end',   source: 'voice',     ts: ago(85_000),  payload: {} },
    { id: 34, correlation_id: CORR_E, kind: 'orb_state',        source: 'voice',     ts: ago(84_500),  payload: { state: 'idle' } },

    { id: 35, correlation_id: null,   kind: 'error',            source: 'system',    ts: ago(70_000),  payload: { message: 'TTS timeout after 10s', retried: true } },
    { id: 36, correlation_id: null,   kind: 'mcp_call',         source: 'scheduler', ts: ago(60_000),  payload: { tool: 'check_reminders', duration_ms: 33 } },
    { id: 37, correlation_id: null,   kind: 'mcp_call',         source: 'scheduler', ts: ago(55_000),  payload: { tool: 'check_reminders', duration_ms: 28 } },
    { id: 38, correlation_id: null,   kind: 'orb_state',        source: 'system',    ts: ago(50_000),  payload: { state: 'listening' } },
    { id: 39, correlation_id: null,   kind: 'orb_state',        source: 'system',    ts: ago(49_500),  payload: { state: 'idle' } },
    { id: 40, correlation_id: null,   kind: 'panel_open',       source: 'hud',       ts: ago(40_000),  payload: { panel: 'log' } },
    { id: 41, correlation_id: null,   kind: 'panel_close',      source: 'hud',       ts: ago(35_000),  payload: { panel: 'log' } },
    { id: 42, correlation_id: null,   kind: 'mcp_call',         source: 'scheduler', ts: ago(30_000),  payload: { tool: 'get_spotify_status', duration_ms: 55 } },
    { id: 43, correlation_id: null,   kind: 'orb_state',        source: 'system',    ts: ago(20_000),  payload: { state: 'listening' } },
    { id: 44, correlation_id: null,   kind: 'orb_state',        source: 'system',    ts: ago(19_000),  payload: { state: 'idle' } },
    { id: 45, correlation_id: null,   kind: 'mcp_call',         source: 'system',    ts: ago(15_000),  payload: { tool: 'get_ha_status', duration_ms: 67 } },
    { id: 46, correlation_id: null,   kind: 'tts_emitted',      source: 'voice',     ts: ago(10_000),  payload: { char_count: 41, duration_ms: 1100, voice_id: 'fish-v1' } },
    { id: 47, correlation_id: null,   kind: 'orb_state',        source: 'system',    ts: ago(9_000),   payload: { state: 'speaking' } },
    { id: 48, correlation_id: null,   kind: 'orb_state',        source: 'system',    ts: ago(8_000),   payload: { state: 'idle' } },
    { id: 49, correlation_id: null,   kind: 'panel_open',       source: 'hud',       ts: ago(5_000),   payload: { panel: 'ledger' } },
    { id: 50, correlation_id: null,   kind: 'voice_turn_start', source: 'voice',     ts: ago(2_000),   payload: {} },
];

export const MOCK_VOICE_COMPOSER_STATUS: VoiceComposerStatus = {
    last_compose_ts: ago(2_000),
    last_salutation: 'Sir',
};

export const MOCK_COUNTS_24H: LedgerKindCounts = {
    tts_emitted: 12,
    mcp_call: 31,
    wake_word: 8,
    orb_state: 22,
    panel_open: 9,
    panel_close: 9,
    barge_in: 2,
    voice_turn_start: 8,
    voice_turn_end: 7,
    error: 1,
};

export const MOCK_BRAIN_INSPECTOR_PAYLOAD: BrainInspectorPayload = {
    voice_composer_status: MOCK_VOICE_COMPOSER_STATUS,
    ledger_recent: MOCK_DEVICE_EVENTS.slice(0, 10),
    ledger_count_24h: MOCK_COUNTS_24H,
};

export const MOCK_BRAIN_STATE: BrainState = {
    voiceComposerStatus: MOCK_VOICE_COMPOSER_STATUS,
    recent: [...MOCK_DEVICE_EVENTS].sort((a, b) => b.ts.localeCompare(a.ts)),
    counts24h: MOCK_COUNTS_24H,
    filter: { kinds: [], sinceMs: null },
    lastInspectorTs: ago(2_000),
};
