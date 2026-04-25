/**
 * Log feature types.
 */

/** Log severity levels emitted by the backend loguru sink. */
export type LogLevel = 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';

/**
 * A single backend log line broadcast via the ``log_line`` WS message type.
 * All timestamps are Unix epoch milliseconds.
 */
export interface LogLinePayload {
    timestamp: number;
    level: LogLevel;
    module: string;
    message: string;
}

/**
 * Per-voice-turn latency breakdown broadcast via the ``turn_timing`` WS message.
 * All ``*_ts`` fields are Unix epoch milliseconds. Fields may be ``null`` when
 * a phase was skipped (e.g. no TTS audio produced for a sleep-phrase turn).
 */
export interface TurnTimingPayload {
    turn_id: string;
    /** Epoch ms when the audio buffer was handed off to STT. */
    audio_end_ts: number;
    /** Epoch ms when STT returned a transcript. */
    stt_done_ts: number;
    /** Epoch ms when the first LLM text token arrived (TTFT). Null if cancelled. */
    llm_first_token_ts: number | null;
    /** Epoch ms when the full LLM response stream completed. */
    llm_done_ts: number;
    /** Epoch ms when the first TTS audio chunk was broadcast. Null if no audio. */
    tts_first_audio_ts: number | null;
    /** Epoch ms when TTS stream ended (last chunk broadcast). */
    tts_done_ts: number;
}
