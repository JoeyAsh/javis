/**
 * JARVIS SFX configuration.
 *
 * All paths are relative to `public/sounds/`. The audio engine resolves
 * them at runtime. If a file is missing the engine logs a warning and
 * silently skips the event — no throws.
 *
 * Batch 1 events: boot, wakeWord, scan, confirm, error, transition,
 *   ambient, drag_start, drag_end, resize, pin, unpin, expand, collapse,
 *   click, hover.
 *
 * Batch 2 events (SFX #34): boot_complete, shutdown, wake, state_change,
 *   mic_open, mic_close, speech_start, speech_end, barge_in, offline,
 *   disconnect, thinking, working, idle_pulse, heartbeat, menu_open,
 *   menu_close, transition_1, transition_2.
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
  /**
   * Optional gain override when ducking is active (overrides the global
   * DUCK_VOLUME constant). Used for the ambient loop which should duck to
   * near-silence rather than the standard 12 %.
   */
  duckedVolume?: number;
}

export type SfxEvent =
  // ── Batch 1 ────────────────────────────────────────────────────────────────
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
  | 'hover'
  // ── Batch 2 ────────────────────────────────────────────────────────────────
  | 'boot_complete'
  | 'shutdown'
  | 'wake'
  | 'state_change'
  | 'mic_open'
  | 'mic_close'
  | 'speech_start'
  | 'speech_end'
  | 'barge_in'
  | 'offline'
  | 'disconnect'
  | 'thinking'
  | 'working'
  | 'idle_pulse'
  | 'heartbeat'
  | 'menu_open'
  | 'menu_close'
  | 'transition_1'
  | 'transition_2';

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
 *   - ambient: 25 %, duckable (background loop), duckedVolume: 5 %
 *   - scan: 70 %, duckable (scanning loop during thinking)
 *   - thinking / working: looping ambient cognition layers, duckable
 *   - boot / confirm / error / transition / wakeWord: full or near-full, not duckable
 */
export const SFX_CONFIG: Record<SfxEvent, SfxEntry> = {
  // ── Batch 1 ──────────────────────────────────────────────────────────────
  boot: {
    file: 'boot/boot_3.mp3',
    loop: false,
    volume: 1.0,
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
    file: 'ambient/ambient_2.mp3',
    loop: true,
    volume: 0.25,
    duckable: true,
    duckedVolume: 0.05,
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
  // ── Batch 2 ──────────────────────────────────────────────────────────────
  boot_complete: {
    file: 'boot/boot_complete_1.mp3',
    loop: false,
    volume: 0.85,
    duckable: false,
  },
  shutdown: {
    file: 'shutdown/shutdown_1.mp3',
    loop: false,
    volume: 0.80,
    duckable: false,
  },
  wake: {
    file: 'wake/wake_2.mp3',
    loop: false,
    volume: 0.85,
    duckable: false,
  },
  state_change: {
    file: 'state_change/state_change_1.mp3',
    loop: false,
    volume: 0.60,
    duckable: false,
  },
  mic_open: {
    file: 'mic_open/mic_open_1.mp3',
    loop: false,
    volume: 0.70,
    duckable: false,
  },
  mic_close: {
    file: 'mic_close/mic_close_1.mp3',
    loop: false,
    volume: 0.70,
    duckable: false,
  },
  speech_start: {
    file: 'speech_start/speech_start_1.mp3',
    loop: false,
    volume: 0.65,
    duckable: false,
  },
  speech_end: {
    file: 'speech_end/speech_end_1.mp3',
    loop: false,
    volume: 0.65,
    duckable: false,
  },
  barge_in: {
    file: 'barge_in/barge_in_1.mp3',
    loop: false,
    volume: 0.75,
    duckable: false,
  },
  offline: {
    file: 'offline/offline_1.mp3',
    loop: false,
    volume: 0.80,
    duckable: false,
  },
  disconnect: {
    file: 'disconnect/disconnect_1.mp3',
    loop: false,
    volume: 0.75,
    duckable: false,
  },
  thinking: {
    file: 'thinking/thinking_1.mp3',
    loop: true,
    volume: 0.55,
    duckable: true,
  },
  working: {
    file: 'working/working_1.mp3',
    loop: true,
    volume: 0.55,
    duckable: true,
  },
  idle_pulse: {
    file: 'idle_pulse/idle_pulse_1.mp3',
    loop: true,
    volume: 0.20,
    duckable: true,
  },
  heartbeat: {
    file: 'heartbeat/heartbeat_1.mp3',
    loop: true,
    volume: 0.15,
    duckable: true,
  },
  menu_open: {
    file: 'menu/menu_open_1.mp3',
    loop: false,
    volume: 0.60,
    duckable: false,
  },
  menu_close: {
    file: 'menu/menu_close_1.mp3',
    loop: false,
    volume: 0.60,
    duckable: false,
  },
  transition_1: {
    file: 'transition/transition_1.mp3',
    loop: false,
    volume: 0.70,
    duckable: false,
  },
  transition_2: {
    file: 'transition/transition_2.mp3',
    loop: false,
    volume: 0.70,
    duckable: false,
  },
};
