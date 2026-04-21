/**
 * JARVIS SFX configuration.
 *
 * All paths are relative to `public/sounds/`. The audio engine resolves
 * them at runtime. If a file is missing the engine logs a warning and
 * silently skips the event — no throws.
 */

export interface SfxEntry {
  /** Path relative to `public/sounds/`. */
  file: string;
  /** Whether to loop this sound until explicitly stopped. */
  loop: boolean;
  /** Gain 0–1. */
  volume: number;
  /** Whether this sound is ducked when `setDucking(true)` is called. */
  duckable: boolean;
}

export type SfxEvent =
  | 'boot'
  | 'wakeWord'
  | 'scan'
  | 'confirm'
  | 'error'
  | 'transition'
  | 'ambient'
  | 'drag_start'
  | 'drag_end'
  | 'resize'
  | 'pin'
  | 'unpin'
  | 'expand'
  | 'collapse'
  | 'click'
  | 'hover';

/** Gain applied to duckable loops when ducking is active. */
export const DUCK_VOLUME = 0.12;

/** Linear-ramp duration (ms) for duck in/out transitions. */
export const DUCK_RAMP_MS = 200;

/**
 * Default SFX mapping.
 *
 * Volumes and duckable flags per spec:
 *   - click: 50 %, not duckable (one-shot UI feedback)
 *   - hover: 30 %, not duckable
 *   - drag_start / drag_end: 60 %, not duckable
 *   - resize: 55 %, not duckable
 *   - pin / unpin / expand / collapse: 65 %, not duckable
 *   - ambient: 40 %, duckable (background loop)
 *   - scan: 70 %, duckable (scanning loop during thinking)
 *   - boot / confirm / error / transition / wakeWord: full or near-full, not duckable
 */
export const SFX_CONFIG: Record<SfxEvent, SfxEntry> = {
  boot: {
    file: 'boot/boot_1.mp3',
    loop: false,
    volume: 0.85,
    duckable: false,
  },
  wakeWord: {
    file: 'wake/wake_1.mp3',
    loop: false,
    volume: 0.80,
    duckable: false,
  },
  scan: {
    file: 'scan/scan_1.mp3',
    loop: true,
    volume: 0.70,
    duckable: true,
  },
  confirm: {
    file: 'confirm/confirm_1.mp3',
    loop: false,
    volume: 0.80,
    duckable: false,
  },
  error: {
    file: 'error/error_1.mp3',
    loop: false,
    volume: 0.80,
    duckable: false,
  },
  transition: {
    file: 'transition/transition_1.mp3',
    loop: false,
    volume: 0.75,
    duckable: false,
  },
  ambient: {
    file: 'ambient/ambient_1.mp3',
    loop: true,
    volume: 0.40,
    duckable: true,
  },
  drag_start: {
    file: 'drag_start/drag_start_1.mp3',
    loop: false,
    volume: 0.60,
    duckable: false,
  },
  drag_end: {
    file: 'drag_end/drag_end_1.mp3',
    loop: false,
    volume: 0.60,
    duckable: false,
  },
  resize: {
    file: 'resize/resize_1.mp3',
    loop: false,
    volume: 0.55,
    duckable: false,
  },
  pin: {
    file: 'pin/pin_1.mp3',
    loop: false,
    volume: 0.65,
    duckable: false,
  },
  unpin: {
    file: 'unpin/unpin_1.mp3',
    loop: false,
    volume: 0.65,
    duckable: false,
  },
  expand: {
    file: 'expand/expand_1.mp3',
    loop: false,
    volume: 0.65,
    duckable: false,
  },
  collapse: {
    file: 'collapse/collapse_1.mp3',
    loop: false,
    volume: 0.65,
    duckable: false,
  },
  click: {
    file: 'click/click_1.mp3',
    loop: false,
    volume: 0.50,
    duckable: false,
  },
  hover: {
    file: 'hover/hover_1.mp3',
    loop: false,
    volume: 0.30,
    duckable: false,
  },
};
