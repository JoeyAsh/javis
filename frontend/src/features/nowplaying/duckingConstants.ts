/**
 * Audio-ducking configuration defaults for the JARVIS conversation flow.
 * These values mirror the `narration.ducking.*` config block in config.yaml.
 * Config-yaml wiring is a follow-up; hardcoded defaults are used for now.
 */

export const DUCKING_FACTORS = {
    spotify: 0.25,
    sfx: 0.12,
    chime: 0.35,
} as const;

export const DUCKING_RAMP_MS = {
    down: 200,
    up: 400,
} as const;

export const TAIL_SILENCE_MS = 500;
