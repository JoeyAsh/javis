/**
 * Shared types for the JARVIS Web Audio Engine.
 */

/**
 * Contract for any external audible source that wants to participate in
 * unified conversation-state ducking (e.g. the Spotify Web Playback SDK).
 * Registered via `AudioEngine.registerExternalDuckable(source)`.
 */
export interface ExternalDuckable {
    /** Human-readable identifier for debugging. */
    name: string;
    /**
     * Duck the source to `factor * currentVolume` over `rampMs` milliseconds.
     * Should be idempotent: if already ducked, this is a no-op.
     */
    duck(factor: number, rampMs: number): Promise<void>;
    /**
     * Restore the source to its pre-duck volume over `rampMs` milliseconds.
     * Clears the stored pre-duck volume on completion.
     */
    restore(rampMs: number): Promise<void>;
}

/** Target for the unified `setDuckingState` orchestrator. */
export type DuckingTarget = 'duck' | 'restore';

/** Per-source factor bag passed to `setDuckingState`. */
export interface DuckingFactors {
    spotify: number;
    sfx: number;
    chime: number;
}
