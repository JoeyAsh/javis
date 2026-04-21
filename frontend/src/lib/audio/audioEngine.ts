/**
 * JARVIS Web Audio Engine.
 *
 * Graph topology:
 *   one-shots      → sfxGain → masterGain → destination
 *   duckable loops → loopGain → sfxGain ──↗
 *
 * Construction suspends the AudioContext (browser autoplay policy). It is
 * resumed on the first user gesture via `resumeContext()`.
 *
 * Callers interact exclusively via the public API — never touch nodes
 * directly.
 */

import { SFX_CONFIG, DUCK_VOLUME, DUCK_RAMP_MS } from './config';
import type { SfxEvent } from './config';

interface ActiveLoop {
    source: AudioBufferSourceNode;
    gainNode: GainNode;
}

export class AudioEngine {
    private readonly ctx: AudioContext;
    private readonly masterGain: GainNode;
    private readonly sfxGain: GainNode;
    private readonly loopGain: GainNode;

    /** Decoded buffer cache: event → buffer (null = fetch failed). */
    private readonly bufferCache = new Map<SfxEvent, AudioBuffer | null>();

    /** Currently playing loops. */
    private readonly activeLoops = new Map<SfxEvent, ActiveLoop>();

    private _isMuted = false;
    private _isDucked = false;

    /** Whether the browser's `prefers-reduced-motion` is active. */
    private readonly reducedMotion: boolean;

    constructor() {
        this.ctx = new AudioContext();

        this.masterGain = this.ctx.createGain();
        this.masterGain.gain.value = 1;

        this.sfxGain = this.ctx.createGain();
        this.sfxGain.gain.value = 1;

        this.loopGain = this.ctx.createGain();
        this.loopGain.gain.value = 1;

        // Signal chain: loopGain → sfxGain → masterGain → destination
        // This ensures setMuted (which zeros sfxGain) silences duckable loops too.
        this.sfxGain.connect(this.masterGain);
        this.loopGain.connect(this.sfxGain);
        this.masterGain.connect(this.ctx.destination);

        this.reducedMotion =
            typeof window !== 'undefined' &&
            window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }

    // ---------------------------------------------------------------------------
    // Context management
    // ---------------------------------------------------------------------------

    /** Resume the suspended AudioContext (idempotent). */
    async resumeContext(): Promise<void> {
        if (this.ctx.state === 'suspended') {
            try {
                await this.ctx.resume();
            } catch (err) {
                console.warn('[AudioEngine] resumeContext failed:', err);
            }
        }
    }

    // ---------------------------------------------------------------------------
    // Buffer loading
    // ---------------------------------------------------------------------------

    private async loadBuffer(event: SfxEvent): Promise<AudioBuffer | null> {
        const cached = this.bufferCache.get(event);
        if (cached !== undefined) return cached;

        const entry = SFX_CONFIG[event];
        const url = `/sounds/${entry.file}`;

        try {
            const response = await fetch(url);
            if (!response.ok) {
                console.warn(`[AudioEngine] 404 for SFX "${event}" at ${url}`);
                this.bufferCache.set(event, null);
                return null;
            }
            const arrayBuffer = await response.arrayBuffer();
            const decoded = await this.ctx.decodeAudioData(arrayBuffer);
            this.bufferCache.set(event, decoded);
            return decoded;
        } catch (err) {
            console.warn(`[AudioEngine] Failed to load SFX "${event}":`, err);
            this.bufferCache.set(event, null);
            return null;
        }
    }

    // ---------------------------------------------------------------------------
    // Playback
    // ---------------------------------------------------------------------------

    /**
     * Play or start a sound for the given event.
     * - Loop events: starts the loop (idempotent if already running).
     * - One-shot events: plays once.
     */
    play(event: SfxEvent): void {
        const entry = SFX_CONFIG[event];
        if (entry.loop) {
            this.startLoop(event);
        } else {
            this.playOneShot(event);
        }
    }

    /**
     * Stop a looping sound with a 200 ms fade-out. No-op for one-shots.
     */
    stop(event: SfxEvent): void {
        const loop = this.activeLoops.get(event);
        if (!loop) return;

        const now = this.ctx.currentTime;
        const fadeOutSec = DUCK_RAMP_MS / 1000;
        loop.gainNode.gain.setValueAtTime(loop.gainNode.gain.value, now);
        loop.gainNode.gain.linearRampToValueAtTime(0, now + fadeOutSec);

        const source = loop.source;
        setTimeout(() => {
            try {
                source.stop();
                source.disconnect();
                loop.gainNode.disconnect();
            } catch {
                // Already stopped — safe to ignore.
            }
        }, DUCK_RAMP_MS + 50);

        this.activeLoops.delete(event);
    }

    /**
     * Fire-and-forget one-shot playback.
     * @param overrideFile Optional path override (relative to `public/sounds/`).
     */
    playOneShot(event: SfxEvent, overrideFile?: string): void {
        void this.fireOneShot(event, overrideFile);
    }

    private async fireOneShot(event: SfxEvent, overrideFile?: string): Promise<void> {
        if (this.ctx.state !== 'running') return;

        let buffer: AudioBuffer | null;
        if (overrideFile !== undefined) {
            // Load override directly without touching the cache for the event key.
            try {
                const response = await fetch(`/sounds/${overrideFile}`);
                if (!response.ok) {
                    console.warn(`[AudioEngine] 404 override at /sounds/${overrideFile}`);
                    return;
                }
                const ab = await response.arrayBuffer();
                // Post-await re-check: ctx may have been closed during the async fetch.
                if (this.ctx.state !== 'running') return;
                buffer = await this.ctx.decodeAudioData(ab);
            } catch (err) {
                console.warn('[AudioEngine] Override load failed:', err);
                return;
            }
        } else {
            buffer = await this.loadBuffer(event);
        }

        if (!buffer) return;

        // Post-await re-check: ctx may have been closed or suspended during the
        // async load (e.g. React StrictMode unmount, or tab backgrounded).
        if (this.ctx.state !== 'running') return;

        const entry = SFX_CONFIG[event];
        const gainNode = this.ctx.createGain();
        gainNode.gain.value = entry.volume;

        const source = this.ctx.createBufferSource();
        source.buffer = buffer;
        source.connect(gainNode);
        // One-shots connect directly to sfxGain (not loopGain).
        gainNode.connect(this.sfxGain);
        source.start();

        source.onended = () => {
            source.disconnect();
            gainNode.disconnect();
        };
    }

    private startLoop(event: SfxEvent): void {
        // `prefers-reduced-motion` suppresses ambient/idle loops.
        if (this.reducedMotion) return;

        if (this.activeLoops.has(event)) return; // Already running, idempotent.

        void this.launchLoop(event);
    }

    private async launchLoop(event: SfxEvent): Promise<void> {
        // Pre-check: bail if not running (suspended or closed).
        if (this.ctx.state !== 'running') return;

        const buffer = await this.loadBuffer(event);
        if (!buffer) return;

        // Post-await re-check: ctx may have been closed or suspended during the
        // async load (e.g. during React StrictMode unmount, or tab backgrounded).
        if (this.ctx.state !== 'running') return;

        // Guard: another caller may have started the loop while we awaited.
        if (this.activeLoops.has(event)) return;

        const entry = SFX_CONFIG[event];

        const gainNode = this.ctx.createGain();
        gainNode.gain.value = entry.volume * (this._isDucked ? DUCK_VOLUME : 1);

        const source = this.ctx.createBufferSource();
        source.buffer = buffer;
        source.loop = true;

        source.connect(gainNode);
        // Duckable loops go through loopGain.
        if (entry.duckable) {
            gainNode.connect(this.loopGain);
        } else {
            gainNode.connect(this.sfxGain);
        }

        source.start();
        this.activeLoops.set(event, { source, gainNode });
    }

    // ---------------------------------------------------------------------------
    // Ducking
    // ---------------------------------------------------------------------------

    /**
     * Duck duckable loop gain down to `DUCK_VOLUME` or restore to 1.
     * Uses a linearRamp over `DUCK_RAMP_MS` milliseconds.
     */
    setDucking(active: boolean): void {
        if (this._isDucked === active) return;
        this._isDucked = active;

        const target = active ? DUCK_VOLUME : 1;
        const now = this.ctx.currentTime;
        const rampSec = DUCK_RAMP_MS / 1000;

        this.loopGain.gain.cancelScheduledValues(now);
        this.loopGain.gain.setValueAtTime(this.loopGain.gain.value, now);
        this.loopGain.gain.linearRampToValueAtTime(target, now + rampSec);
    }

    // ---------------------------------------------------------------------------
    // Mute
    // ---------------------------------------------------------------------------

    /** Toggle all SFX output (master sfxGain). */
    setMuted(muted: boolean): void {
        this._isMuted = muted;
        const now = this.ctx.currentTime;
        this.sfxGain.gain.cancelScheduledValues(now);
        this.sfxGain.gain.setValueAtTime(muted ? 0 : 1, now);
    }

    get isMuted(): boolean {
        return this._isMuted;
    }

    // ---------------------------------------------------------------------------
    // Lifecycle
    // ---------------------------------------------------------------------------

    /** Stop all loops, disconnect all nodes, close the AudioContext. */
    destroy(): void {
        for (const event of this.activeLoops.keys()) {
            this.stop(event);
        }
        try {
            this.masterGain.disconnect();
            this.sfxGain.disconnect();
            this.loopGain.disconnect();
        } catch {
            // Already disconnected.
        }
        void this.ctx.close();
    }
}

// ---------------------------------------------------------------------------
// Module-level singleton
// ---------------------------------------------------------------------------

/**
 * Module-level singleton. The AudioContext lives for the page lifetime —
 * creating multiple instances (e.g. via React StrictMode's double-invoke)
 * would close the ctx on the first cleanup and break all subsequent usage.
 * Every mount of `useAudioEngine` reuses the same engine.
 */
let __singleton: AudioEngine | null = null;

export function getAudioEngine(): AudioEngine {
    if (__singleton === null) {
        __singleton = new AudioEngine();
    }
    return __singleton;
}

/**
 * TEST-ONLY: reset the module singleton.
 *
 * Call this in `afterEach` to restore test isolation. Do not call from
 * application code — it closes the AudioContext and discards all state.
 */
export function __resetAudioEngineSingleton(): void {
    if (__singleton !== null) {
        try {
            __singleton.destroy();
        } catch {
            // Ignore — context may already be closed.
        }
        __singleton = null;
    }
}
