/**
 * JARVIS Web Audio Engine.
 * Copy of src/lib/audio/audioEngine.ts — original remains in place.
 *
 * Graph topology:
 *   one-shots      → sfxGain → masterGain → destination
 *   duckable loops → loopGain → sfxGain ──↗
 */

import { SFX_CONFIG, DUCK_VOLUME, DUCK_RAMP_MS } from './config';
import type { SfxEvent } from './config';
import type { ExternalDuckable, DuckingTarget, DuckingFactors } from './audioEngine.types';

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

    /** External duckable sources registered via registerExternalDuckable(). */
    private readonly externalDuckables = new Map<string, ExternalDuckable>();

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

        this.sfxGain.connect(this.masterGain);
        this.loopGain.connect(this.sfxGain);
        this.masterGain.connect(this.ctx.destination);

        this.reducedMotion =
            typeof window !== 'undefined' &&
            window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }

    async resumeContext(): Promise<void> {
        if (this.ctx.state === 'suspended') {
            try {
                await this.ctx.resume();
            } catch (err) {
                console.warn('[AudioEngine] resumeContext failed:', err);
            }
        }
    }

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

    play(event: SfxEvent): void {
        const entry = SFX_CONFIG[event];
        if (entry.loop) {
            this.startLoop(event);
        } else {
            this.playOneShot(event);
        }
    }

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

    playOneShot(event: SfxEvent, overrideFile?: string): void {
        void this.fireOneShot(event, overrideFile);
    }

    private async fireOneShot(event: SfxEvent, overrideFile?: string): Promise<void> {
        if (this.ctx.state !== 'running') return;

        let buffer: AudioBuffer | null;
        if (overrideFile !== undefined) {
            try {
                const response = await fetch(`/sounds/${overrideFile}`);
                if (!response.ok) {
                    console.warn(`[AudioEngine] 404 override at /sounds/${overrideFile}`);
                    return;
                }
                const ab = await response.arrayBuffer();
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
        if (this.ctx.state !== 'running') return;

        const entry = SFX_CONFIG[event];
        const gainNode = this.ctx.createGain();
        gainNode.gain.value = entry.volume;

        const source = this.ctx.createBufferSource();
        source.buffer = buffer;
        source.connect(gainNode);
        gainNode.connect(this.sfxGain);
        source.start();

        source.onended = () => {
            source.disconnect();
            gainNode.disconnect();
        };
    }

    private startLoop(event: SfxEvent): void {
        if (this.reducedMotion) return;
        if (this.activeLoops.has(event)) return;
        void this.launchLoop(event);
    }

    private async launchLoop(event: SfxEvent): Promise<void> {
        if (this.ctx.state !== 'running') return;

        const buffer = await this.loadBuffer(event);
        if (!buffer) return;

        if (this.ctx.state !== 'running') return;
        if (this.activeLoops.has(event)) return;

        const entry = SFX_CONFIG[event];

        const gainNode = this.ctx.createGain();
        gainNode.gain.value = entry.volume * (this._isDucked ? DUCK_VOLUME : 1);

        const source = this.ctx.createBufferSource();
        source.buffer = buffer;
        source.loop = true;

        source.connect(gainNode);
        if (entry.duckable) {
            gainNode.connect(this.loopGain);
        } else {
            gainNode.connect(this.sfxGain);
        }

        source.start();
        this.activeLoops.set(event, { source, gainNode });
    }

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

    /**
     * Register an external audible source (e.g. Spotify SDK) to participate
     * in unified conversation-state ducking.
     * Returns an unsubscribe function — call it on cleanup.
     */
    registerExternalDuckable(source: ExternalDuckable): () => void {
        this.externalDuckables.set(source.name, source);
        return () => {
            this.externalDuckables.delete(source.name);
        };
    }

    /**
     * Unified ducking orchestrator — fans out to internal SFX/chime gain AND
     * all registered external duckables.
     *
     * `factors.sfx` / `factors.chime` map to the internal `loopGain` (the
     * existing `setDucking` path). `factors.spotify` is forwarded to any
     * registered ExternalDuckable with name === 'spotify'.
     */
    setDuckingState(
        target: DuckingTarget,
        factors: DuckingFactors,
        rampMs: number,
    ): void {
        // Internal SFX / chime via the existing loopGain path.
        // We use `factors.sfx` as the duck factor for the internal gain node.
        if (target === 'duck') {
            if (!this._isDucked) {
                this._isDucked = true;
                const now = this.ctx.currentTime;
                const rampSec = rampMs / 1000;
                this.loopGain.gain.cancelScheduledValues(now);
                this.loopGain.gain.setValueAtTime(this.loopGain.gain.value, now);
                this.loopGain.gain.linearRampToValueAtTime(factors.sfx, now + rampSec);
            }
        } else {
            if (this._isDucked) {
                this._isDucked = false;
                const now = this.ctx.currentTime;
                const rampSec = rampMs / 1000;
                this.loopGain.gain.cancelScheduledValues(now);
                this.loopGain.gain.setValueAtTime(this.loopGain.gain.value, now);
                this.loopGain.gain.linearRampToValueAtTime(1, now + rampSec);
            }
        }

        // Fan out to registered external duckables.
        this.externalDuckables.forEach((source) => {
            // Determine the factor for this named source.
            const factor =
                source.name === 'spotify'
                    ? factors.spotify
                    : source.name === 'chime'
                      ? factors.chime
                      : factors.sfx;

            if (target === 'duck') {
                void source.duck(factor, rampMs);
            } else {
                void source.restore(rampMs);
            }
        });
    }

    setMuted(muted: boolean): void {
        this._isMuted = muted;
        const now = this.ctx.currentTime;
        this.sfxGain.gain.cancelScheduledValues(now);
        this.sfxGain.gain.setValueAtTime(muted ? 0 : 1, now);
    }

    get isMuted(): boolean {
        return this._isMuted;
    }

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

let __singleton: AudioEngine | null = null;

export function getAudioEngine(): AudioEngine {
    if (__singleton === null) {
        __singleton = new AudioEngine();
    }
    return __singleton;
}

/** TEST-ONLY: reset the module singleton. */
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
