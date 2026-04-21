/**
 * JARVIS — Multi-mode particle visualization.
 *
 * Floating particles with line connections between nearby ones.
 * Lines fade in/out based on state. Transition tumble on state change.
 * Speaking pulls particles closer for denser connections.
 *
 * Based on ethanplusai/jarvis reference implementation.
 */

import * as THREE from 'three';
import type { OrbState } from '../types';

export interface Orb {
    setState(s: OrbState): void;
    setAnalyser(a: AnalyserNode | null): void;
    /**
     * Dev preview: when set to a non-null state, the engine synthesises
     * internal bass/mid amplitude patterns appropriate for that state so the
     * visualisation reacts even without a live audio source. Passing `null`
     * restores normal (analyser-driven) behaviour.
     */
    setMockMode(m: OrbState | null): void;
    /**
     * Conversation-mode follow-up overlay.
     *
     * While `active` is true the orb pulses at a subtler amplitude than
     * full `listening`, signalling that the mic is still open without
     * the wake word. In the last 5 s of the window, a thin accent-coloured
     * ring circumscribes the orb and visibly ticks from full → empty as
     * `seconds` counts down. When `active` flips false, the ring fades
     * out smoothly (~180 ms) and the orb returns to its baseline pulse.
     */
    setFollowUp(active: boolean, seconds: number): void;
    destroy(): void;
}

/** Build a 64×64 soft-glow circular texture for PointsMaterial. */
function createGlowTexture(): THREE.Texture {
    const size = 64;
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d')!;
    const center = size / 2;
    const grad = ctx.createRadialGradient(center, center, 0, center, center, center);
    grad.addColorStop(0, 'rgba(255,255,255,1.0)');
    grad.addColorStop(0.4, 'rgba(255,255,255,0.6)');
    grad.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, size, size);
    const tex = new THREE.CanvasTexture(canvas);
    return tex;
}

export interface CreateOrbOptions {
    /** When true, renderer uses a transparent canvas background (alpha channel enabled). */
    alpha?: boolean;
}

export function createOrb(canvas: HTMLCanvasElement, options: CreateOrbOptions = {}): Orb {
    const { alpha = false } = options;
    let destroyed = false;
    const N = 2000;

    const renderer = new THREE.WebGLRenderer({
        canvas,
        antialias: true,
        alpha,
        premultipliedAlpha: !alpha,
    });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(window.innerWidth, window.innerHeight);
    // When alpha is enabled, clear to transparent so the scene shows through.
    if (alpha) {
        renderer.setClearColor(0x000000, 0);
    } else {
        renderer.setClearColor(0x050508, 1);
    }

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 1, 1000);
    camera.position.z = 80;

    // Shared glow texture — used by both particle systems.
    const glowTex = createGlowTexture();

    // ── Main Particles ──
    const geo = new THREE.BufferGeometry();
    const pos = new Float32Array(N * 3);
    const vel = new Float32Array(N * 3);
    const phase = new Float32Array(N);
    /** Per-particle brightness multiplier in [0.7, 1.0] for subtle colour variation. */
    const brightness = new Float32Array(N);

    /**
     * Per-particle preferred radius fraction in (0, 1]. The shell attractor
     * pulls each particle toward `rFrac * renderRadius` rather than a single
     * shell, which keeps the cloud volumetric (looks like an orb, not a bubble).
     * Weighted with sqrt to bias particles toward the outer layers for a denser
     * visible surface while still filling the interior.
     */
    const rFrac = new Float32Array(N);

    for (let i = 0; i < N; i++) {
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.acos(2 * Math.random() - 1);
        const frac = 0.35 + Math.pow(Math.random(), 0.5) * 0.65; // [0.35, 1.0]
        const r = frac * 25;
        pos[i * 3] = r * Math.sin(phi) * Math.cos(theta);
        pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
        pos[i * 3 + 2] = r * Math.cos(phi);
        phase[i] = Math.random() * 1000;
        brightness[i] = 0.7 + Math.random() * 0.3; // range [0.7, 1.0]
        rFrac[i] = frac;
    }

    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));

    const mat = new THREE.PointsMaterial({
        color: 0x4ca8e8,
        size: 0.6, // was 0.4 — larger so the glow is visible
        transparent: true,
        opacity: 0.6,
        sizeAttenuation: true,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        map: glowTex,
        alphaTest: 0.001,
    });

    const points = new THREE.Points(geo, mat);
    scene.add(points);

    // ── Core Glow Particles (~200 tightly-packed bright particles at radius 0–5) ──
    const CORE_N = 200;
    const coreGeo = new THREE.BufferGeometry();
    const corePos = new Float32Array(CORE_N * 3);

    for (let i = 0; i < CORE_N; i++) {
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.acos(2 * Math.random() - 1);
        const r = Math.random() * 5;
        corePos[i * 3] = r * Math.sin(phi) * Math.cos(theta);
        corePos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
        corePos[i * 3 + 2] = r * Math.cos(phi);
    }

    coreGeo.setAttribute('position', new THREE.BufferAttribute(corePos, 3));

    const coreMat = new THREE.PointsMaterial({
        color: 0x8dd4ff,
        size: 1.2,
        transparent: true,
        opacity: 0.9,
        sizeAttenuation: true,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        map: glowTex,
        alphaTest: 0.001,
    });

    const corePoints = new THREE.Points(coreGeo, coreMat);
    scene.add(corePoints);

    // ── Connection lines ──
    const MAX_LINES = 8000;
    const linePos = new Float32Array(MAX_LINES * 6);
    const lineGeo = new THREE.BufferGeometry();
    lineGeo.setAttribute('position', new THREE.BufferAttribute(linePos, 3));
    lineGeo.setDrawRange(0, 0);

    const lineMat = new THREE.LineBasicMaterial({
        color: 0x4ca8e8,
        transparent: true,
        opacity: 0.0,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
    });

    const lines = new THREE.LineSegments(lineGeo, lineMat);
    scene.add(lines);

    // ── Electrons — bright dots that travel along connections ──
    const MAX_ELECTRONS = 200;
    const electronGeo = new THREE.BufferGeometry();
    const electronPos = new Float32Array(MAX_ELECTRONS * 3);
    electronGeo.setAttribute('position', new THREE.BufferAttribute(electronPos, 3));
    electronGeo.setDrawRange(0, 0);

    const electronMat = new THREE.PointsMaterial({
        color: 0xffffff,
        size: 0.8,
        transparent: true,
        opacity: 1.0,
        sizeAttenuation: true,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        map: glowTex,
        alphaTest: 0.001,
    });

    const electronsMesh = new THREE.Points(electronGeo, electronMat);
    scene.add(electronsMesh);

    // ── Follow-up countdown ring ──
    // Thin accent-coloured ring at ~1.15× the orb's render radius, drawn
    // only during the follow-up window. Last 5 s of the window: drawRange
    // animates from a full circle down to zero, ticking to indicate the
    // remaining time. Additive to the particle engine — this is a separate
    // LineLoop with its own material, it never touches `points`/`lines`.
    const RING_SEGMENTS = 128;
    const ringGeo = new THREE.BufferGeometry();
    const ringPos = new Float32Array((RING_SEGMENTS + 1) * 3);
    for (let i = 0; i <= RING_SEGMENTS; i++) {
        const a = (i / RING_SEGMENTS) * Math.PI * 2;
        ringPos[i * 3] = Math.cos(a);
        ringPos[i * 3 + 1] = Math.sin(a);
        ringPos[i * 3 + 2] = 0;
    }
    ringGeo.setAttribute('position', new THREE.BufferAttribute(ringPos, 3));
    ringGeo.setDrawRange(0, RING_SEGMENTS + 1);

    const ringMat = new THREE.LineBasicMaterial({
        color: 0x4ca8e8, // matches --accent
        transparent: true,
        opacity: 0.0,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
    });
    const ring = new THREE.Line(ringGeo, ringMat);
    scene.add(ring);

    interface ElectronData {
        sx: number;
        sy: number;
        sz: number;
        ex: number;
        ey: number;
        ez: number;
        t: number;
        speed: number;
    }
    const activeElectrons: ElectronData[] = [];
    let electronSpawnRate = 0;
    let targetElectronRate = 0;
    let lastElectronSpawn = 0;

    let activeConnections: {
        x1: number;
        y1: number;
        z1: number;
        x2: number;
        y2: number;
        z2: number;
    }[] = [];

    // ── State ──
    let state: OrbState = 'idle';
    let targetRadius = 25,
        currentRadius = 25;
    let targetSpeed = 0.3,
        currentSpeed = 0.3;
    let targetBright = 0.6,
        currentBright = 0.6;
    let targetSize = 0.6,
        currentSize = 0.6;
    let lineAmount = 0,
        targetLineAmount = 0;
    /** Smoothly lerped line opacity — avoids hard jumps when lineAmount changes. */
    let currentLineOpacity = 0;
    const lineDistance = 8;

    let spinX = 0,
        spinY = 0,
        spinZ = 0;
    let transitionEnergy = 0;
    let lastState: OrbState = 'idle';

    let cloudZ = 0,
        cloudZVel = 0;

    // ── Audio ──
    let analyser: AnalyserNode | null = null;
    let freqData = new Uint8Array(64);
    let bass = 0,
        mid = 0;
    /** Low-pass smoothed amplitude driver for speaking scale (prevents snap/overshoot). */
    let smoothedAmp = 0;

    // ── Dev mock mode ──
    // When set to a non-null state, the engine synthesises internal bass/mid
    // values so the visualisation looks alive even without real audio input.
    // Primary use: the HUD's dev-menu test buttons — so the user can preview
    // how each state looks with representative motion/amplitude.
    let mockMode: OrbState | null = null;

    // ── Follow-up countdown ──
    // Driven by the `conversation_mode` WS stream from the backend.
    // `followUpActive` gates the ring's opacity + the orb's muted pulse.
    // `followUpSeconds` is the raw seconds_remaining pushed by the hook
    // (locally interpolated on a 200 ms tick for smoothness).
    let followUpActive = false;
    let followUpSeconds = 0;
    /** Ring opacity target — lerped in animate() so the ring fades smoothly. */
    let ringOpacityTarget = 0;
    /** Current ring opacity — lerps toward ringOpacityTarget at ~180 ms rate. */
    let ringOpacityCurrent = 0;

    const clock = new THREE.Clock();

    // Lerp rate constants — centralised for easy tweaking.
    const LERP_RATE = 0.012;
    const COLOR_LERP = 0.008;
    /** Soft-clip via tanh — keeps amplitude bounded in [0, 1). */
    const softClip = (x: number): number => Math.tanh(x);
    /**
     * Upper bound for orb radius in world units so the rendered orb never
     * exceeds ~65 % of the smaller viewport dimension. Derived from the camera
     * FoV + z distance: visible world half-height at z=0 ≈ tan(22.5°) * 80 ≈
     * 33.14. Target 65 % of viewport height ≈ 0.325 * 33.14 * 2 = ~21.5 radius.
     * We pick 21 for a 63 % cap, which leaves small safety headroom.
     */
    const MAX_RENDER_RADIUS = 27;

    function animate() {
        if (destroyed) return;
        requestAnimationFrame(animate);
        const t = clock.getElapsedTime();

        switch (state) {
            case 'idle':
                // Loose-sphere sweet spot — sits just under MAX_RENDER_RADIUS so the
                // cloud looks generous without clipping.
                targetRadius = 19;
                targetSpeed = 0.28;
                targetBright = 0.5;
                targetSize = 0.55;
                targetLineAmount = 0.15;
                targetElectronRate = 0;
                break;
            case 'listening':
                // "Attentive / receiving" — wider shell, slow drift, sparse web.
                // Breathing pulse applied post-lerp on renderRadius (see below).
                targetRadius = 18;
                targetSpeed = 0.22;
                targetBright = 0.7;
                targetSize = 0.7;
                targetLineAmount = 0.22;
                targetElectronRate = 0;
                break;
            case 'thinking':
                // "Computing" — tight dense core, fast spin, many connections + electrons.
                targetRadius = 12;
                targetSpeed = 0.85;
                targetBright = 0.78;
                targetSize = 0.45;
                targetLineAmount = 1.4;
                targetElectronRate = 0.03;
                break;
            case 'speaking':
                // Baseline small; audio amplitude punches outward up to MAX_RENDER_RADIUS.
                targetRadius = 18;
                targetSpeed = 0.35;
                targetBright = 0.72;
                targetSize = 0.6;
                targetLineAmount = 0.8;
                targetElectronRate = 0;
                break;
            case 'follow_up':
                // Follow-up window — a subtler listening: narrower pulse, dimmer
                // glow, fewer connections. Signals "mic still open" without the
                // full-attention feel of a just-triggered wake word.
                targetRadius = 17;
                targetSpeed = 0.18;
                targetBright = 0.55;
                targetSize = 0.6;
                targetLineAmount = 0.15;
                targetElectronRate = 0;
                break;
        }

        currentRadius += (targetRadius - currentRadius) * LERP_RATE;
        currentSpeed += (targetSpeed - currentSpeed) * LERP_RATE;
        currentBright += (targetBright - currentBright) * LERP_RATE;
        currentSize += (targetSize - currentSize) * LERP_RATE;
        lineAmount += (targetLineAmount - lineAmount) * LERP_RATE;
        electronSpawnRate += (targetElectronRate - electronSpawnRate) * LERP_RATE;

        // Smooth line opacity — lerps independently at a slower rate than other params.
        currentLineOpacity += (lineAmount * 0.18 - currentLineOpacity) * 0.01;

        if (state !== lastState) {
            transitionEnergy = 1.0;
            lastState = state;
        }
        // Faster decay (0.975) + 40% reduced forces → smooth rather than jerky transitions.
        transitionEnergy *= 0.975;
        if (transitionEnergy > 0.05) {
            spinX += transitionEnergy * 0.007 * Math.sin(t * 1.7);
            spinY += transitionEnergy * 0.009;
            spinZ += transitionEnergy * 0.005 * Math.cos(t * 1.3);
        }

        // Audio
        bass = 0;
        mid = 0;
        if (mockMode !== null) {
            // Synthesise plausible bass/mid envelopes so the visualisation reads
            // correctly even without a live audio source (dev-menu preview).
            if (mockMode === 'speaking') {
                // Speech envelope: slow syllable rhythm × faster voicing × occasional bursts.
                const slow = 0.55 + 0.45 * Math.sin(t * 3.1 + Math.sin(t * 0.6) * 2.0);
                const fast = 0.6 + 0.4 * Math.sin(t * 13.5 + Math.sin(t * 2.3));
                const burst = Math.max(0, Math.sin(t * 0.9) - 0.55) * 0.9;
                const env = Math.max(0, Math.min(1, slow * fast + burst));
                bass = env * 0.95;
                mid = Math.max(0, Math.min(1, env * 0.75 + Math.sin(t * 18) * 0.08 + 0.05));
            } else if (mockMode === 'listening') {
                // Attentive low ambient — quiet background with occasional blips.
                bass = 0.04 + Math.max(0, Math.sin(t * 1.3) - 0.6) * 0.15;
                mid = 0.03 + Math.max(0, Math.sin(t * 2.1) - 0.7) * 0.1;
            } else if (mockMode === 'thinking') {
                // Thinking doesn't consume mic; fake subtle internal "activity".
                bass = 0.02 + (Math.sin(t * 5.0) * 0.5 + 0.5) * 0.04;
                mid = 0.02 + (Math.sin(t * 7.0) * 0.5 + 0.5) * 0.03;
            }
            // 'idle' → stays at 0 (default above).
        } else if (analyser) {
            analyser.getByteFrequencyData(freqData);
            let bSum = 0,
                mSum = 0;
            for (let i = 0; i < 8; i++) bSum += freqData[i];
            for (let i = 8; i < 24; i++) mSum += freqData[i];
            bass = bSum / (8 * 255);
            mid = mSum / (16 * 255);
        }

        // Low-pass smoothed amplitude — α ≈ 0.18 on the raw (bass + mid) mix.
        // Soft-clipped with tanh so even very loud peaks stay bounded in [0, 1).
        const rawAmp = softClip(bass * 1.4 + mid * 0.6);
        smoothedAmp += (rawAmp - smoothedAmp) * 0.18;

        // Depth Z breathing — increased spring damping (0.96) and reduced force (0.005).
        let zTarget = Math.sin(t * 0.12) * 8;
        if (state === 'thinking') zTarget = Math.sin(t * 0.3) * 15 + Math.sin(t * 0.9) * 6;
        else if (state === 'speaking') zTarget = Math.sin(t * 0.15) * 6 - smoothedAmp * 6;
        cloudZVel += (zTarget - cloudZ) * 0.005;
        cloudZVel *= 0.96;
        cloudZ += cloudZVel;

        const syncTransform = (obj: THREE.Object3D) => {
            obj.rotation.x = spinX;
            obj.rotation.y = spinY;
            obj.rotation.z = spinZ;
            obj.position.z = cloudZ;
        };
        syncTransform(points);
        syncTransform(lines);
        syncTransform(corePoints);

        // ── Idle breathing pulse ──
        // Slow sine oscillation (~4 s period) modulates opacity and size ±10%.
        const idleBreathAmt = state === 'idle' ? 1.0 : 0.0;
        const idleBreath = 1.0 + idleBreathAmt * 0.1 * Math.sin((t / 4.0) * Math.PI * 2);

        // ── Update particles ──
        const p = geo.getAttribute('position') as THREE.BufferAttribute;
        const a = p.array as Float32Array;

        // Hard clamp on the shell radius so the speaking/bass push cannot grow
        // the orb past ~85 % of the viewport. smoothedAmp already in [0, 1).
        // Listening adds a slow breathing pulse on top of the baseline for an
        // "attentive / receiving" character — purely radial, no amplitude.
        let radiusModifier = 0;
        if (state === 'speaking') radiusModifier = smoothedAmp * 9.0;
        else if (state === 'listening') radiusModifier = Math.sin(t * 0.7) * 1.6;
        const renderRadius = Math.min(currentRadius + radiusModifier, MAX_RENDER_RADIUS);

        // Brownian jitter strength — tiny but enough to keep the cloud alive at idle.
        const jitter = state === 'idle' ? 0.003 : 0.0015;

        for (let i = 0; i < N; i++) {
            const i3 = i * 3;
            const x = a[i3],
                y = a[i3 + 1],
                z = a[i3 + 2];
            const px = phase[i];

            // Noise forces reduced ~30% (0.001 → 0.0007, 0.0008 → 0.00056).
            vel[i3] += Math.sin(t * 0.05 + px) * 0.0007 * currentSpeed;
            vel[i3 + 1] += Math.cos(t * 0.06 + px * 1.3) * 0.0007 * currentSpeed;
            vel[i3 + 2] += Math.sin(t * 0.055 + px * 0.7) * 0.0007 * currentSpeed;
            vel[i3] += Math.sin(t * 0.02 + px * 2.1 + y * 0.1) * 0.00056 * currentSpeed;
            vel[i3 + 1] += Math.cos(t * 0.025 + px * 1.7 + z * 0.1) * 0.00056 * currentSpeed;
            vel[i3 + 2] += Math.sin(t * 0.022 + px * 0.9 + x * 0.1) * 0.00056 * currentSpeed;

            // Brownian jitter — uniformly random kick so the cloud never stalls.
            vel[i3] += (Math.random() - 0.5) * jitter;
            vel[i3 + 1] += (Math.random() - 0.5) * jitter;
            vel[i3 + 2] += (Math.random() - 0.5) * jitter;

            const dist = Math.sqrt(x * x + y * y + z * z) || 0.01;

            // Volumetric shell attractor: each particle has its own preferred
            // radius fraction (rFrac[i]) so the cloud stays volumetric rather than
            // collapsing to a bubble. Pulls from BOTH sides, replacing the constant
            // inward bias that previously collapsed the orb to a point.
            const targetR = rFrac[i] * renderRadius;
            const shellError = dist - targetR;
            const pull = shellError * 0.0022;
            vel[i3] -= (x / dist) * pull;
            vel[i3 + 1] -= (y / dist) * pull;
            vel[i3 + 2] -= (z / dist) * pull;

            if (bass > 0.05) {
                // Clamp to smoothedAmp so loud transients don't blast particles outward.
                // Heavier push in speaking to make amplitude visualisation pop.
                const bassKick = state === 'speaking' ? smoothedAmp * 0.028 : smoothedAmp * 0.012;
                vel[i3] += (x / dist) * bassKick;
                vel[i3 + 1] += (y / dist) * bassKick;
                vel[i3 + 2] += (z / dist) * bassKick;
            }
            if (state === 'speaking' && mid > 0.1) {
                // Per-particle sinusoidal pulse mapped onto shell — creates visible
                // "voicing texture" ripples across the surface.
                const pulse = Math.sin(t * 9 + px * 1.3);
                const midKick = smoothedAmp * 0.018 * pulse;
                vel[i3] += (x / dist) * midKick;
                vel[i3 + 1] += (y / dist) * midKick;
                vel[i3 + 2] += (z / dist) * midKick * 0.6;
            }

            // Reduced damping: 0.992 → 0.985 (particles glide more, less jittery).
            vel[i3] *= 0.985;
            vel[i3 + 1] *= 0.985;
            vel[i3 + 2] *= 0.985;
            a[i3] += vel[i3];
            a[i3 + 1] += vel[i3 + 1];
            a[i3 + 2] += vel[i3 + 2];

            // Hard-clamp particle position so runaway velocities can never escape
            // the MAX_RENDER_RADIUS envelope (safety net against transients).
            const newDist = Math.sqrt(
                a[i3] * a[i3] + a[i3 + 1] * a[i3 + 1] + a[i3 + 2] * a[i3 + 2],
            );
            const hardCap = MAX_RENDER_RADIUS * 1.15;
            if (newDist > hardCap) {
                const k = hardCap / newDist;
                a[i3] *= k;
                a[i3 + 1] *= k;
                a[i3 + 2] *= k;
                // Damp radial velocity component at the boundary.
                vel[i3] *= 0.5;
                vel[i3 + 1] *= 0.5;
                vel[i3 + 2] *= 0.5;
            }
        }
        p.needsUpdate = true;

        // ── Update lines ──
        if (lineAmount > 0.01) {
            const lp = lineGeo.getAttribute('position') as THREE.BufferAttribute;
            const la = lp.array as Float32Array;
            let lineCount = 0;
            const maxDist = lineDistance * (1 + smoothedAmp * 0.4);
            const maxDistSq = maxDist * maxDist;
            const step = Math.max(1, Math.floor(N / 600));

            for (let i = 0; i < N && lineCount < MAX_LINES; i += step) {
                const i3 = i * 3;
                const x1 = a[i3],
                    y1 = a[i3 + 1],
                    z1 = a[i3 + 2];
                for (let j = i + step; j < N && lineCount < MAX_LINES; j += step) {
                    const j3 = j * 3;
                    const dx = a[j3] - x1,
                        dy = a[j3 + 1] - y1,
                        dz = a[j3 + 2] - z1;
                    if (dx * dx + dy * dy + dz * dz < maxDistSq) {
                        const idx = lineCount * 6;
                        la[idx] = x1;
                        la[idx + 1] = y1;
                        la[idx + 2] = z1;
                        la[idx + 3] = a[j3];
                        la[idx + 4] = a[j3 + 1];
                        la[idx + 5] = a[j3 + 2];
                        lineCount++;
                    }
                }
            }
            lineGeo.setDrawRange(0, lineCount * 2);
            lp.needsUpdate = true;
            // Use smoothly-lerped opacity instead of raw lineAmount.
            lineMat.opacity = currentLineOpacity;

            activeConnections = [];
            for (let c = 0; c < Math.min(lineCount, 500); c++) {
                const ci = c * 6;
                activeConnections.push({
                    x1: la[ci],
                    y1: la[ci + 1],
                    z1: la[ci + 2],
                    x2: la[ci + 3],
                    y2: la[ci + 4],
                    z2: la[ci + 5],
                });
            }
        } else {
            lineGeo.setDrawRange(0, 0);
            activeConnections = [];
        }

        // ── Update electrons ──
        if (activeConnections.length > 0 && electronSpawnRate > 0.005) {
            if (activeElectrons.length < 3 && t - lastElectronSpawn > 1.0) {
                const conn =
                    activeConnections[Math.floor(Math.random() * activeConnections.length)];
                activeElectrons.push({
                    sx: conn.x1,
                    sy: conn.y1,
                    sz: conn.z1,
                    ex: conn.x2,
                    ey: conn.y2,
                    ez: conn.z2,
                    t: 0,
                    speed: 0.003 + Math.random() * 0.003,
                });
                lastElectronSpawn = t;
            }
        }

        const ep = electronGeo.getAttribute('position') as THREE.BufferAttribute;
        const ea = ep.array as Float32Array;
        let aliveCount = 0;

        for (let e = activeElectrons.length - 1; e >= 0; e--) {
            const el = activeElectrons[e];
            el.t += el.speed;
            if (el.t >= 1) {
                activeElectrons.splice(e, 1);
                continue;
            }
            const ei = aliveCount * 3;
            ea[ei] = el.sx + (el.ex - el.sx) * el.t;
            ea[ei + 1] = el.sy + (el.ey - el.sy) * el.t;
            ea[ei + 2] = el.sz + (el.ez - el.sz) * el.t;
            aliveCount++;
        }

        electronGeo.setDrawRange(0, aliveCount);
        ep.needsUpdate = true;

        syncTransform(electronsMesh);

        // ── Apply opacity with per-particle brightness variation ──
        // PointsMaterial uses a single opacity for all particles; we modulate by
        // a small sinusoidal shimmer driven by time and the stored per-particle
        // brightness values so different particles visually pulse at different rates.
        // Use smoothedAmp (soft-clipped, LP-filtered) instead of raw bass so loud
        // transients don't cause opacity/size overshoot.
        const baseOpacity = currentBright + smoothedAmp * 0.08;
        // Shimmer: blend base opacity with a per-frame average of brightness offsets
        let shimmerSum = 0;
        for (let i = 0; i < N; i++) {
            shimmerSum += brightness[i] * (0.85 + 0.15 * Math.sin(t * 0.7 + phase[i] * 0.05));
        }
        const shimmerAvg = shimmerSum / N; // stays close to ~0.87
        // Apply idle breathing pulse to opacity and size.
        mat.opacity = baseOpacity * shimmerAvg * idleBreath;
        mat.size = (currentSize + smoothedAmp * 0.04) * idleBreath;

        // ── Core particles per-state heartbeat ──
        // Each state gets its own size / opacity / pulse signature so the centre
        // reads as part of the state rather than static bright dots.
        //  - idle:      dim, barely-there breathing
        //  - listening: muted, slow wider pulse (attentive)
        //  - thinking:  tight bright with fast computation rhythm
        //  - speaking:  bright, amplitude-coupled pulse
        let coreSizeBase: number, coreOpacity: number;
        let corePulsePeriod: number, corePulseAmt: number;
        switch (state) {
            case 'idle':
                coreSizeBase = 0.65;
                coreOpacity = 0.28;
                corePulsePeriod = 4.0;
                corePulseAmt = 0.04;
                break;
            case 'listening':
                coreSizeBase = 0.85;
                coreOpacity = 0.45;
                corePulsePeriod = 2.6;
                corePulseAmt = 0.18;
                break;
            case 'thinking':
                coreSizeBase = 1.1;
                coreOpacity = 0.85;
                corePulsePeriod = 1.1;
                corePulseAmt = 0.28;
                break;
            case 'speaking':
                // Amplitude boosts both brightness and size for visible speech rhythm.
                coreSizeBase = 1.15 + smoothedAmp * 0.6;
                coreOpacity = 0.8 + smoothedAmp * 0.15;
                corePulsePeriod = 2.4;
                corePulseAmt = 0.18;
                break;
            case 'follow_up':
                // Between full listening and idle — still attentive but muted.
                coreSizeBase = 0.75;
                coreOpacity = 0.35;
                corePulsePeriod = 3.2;
                corePulseAmt = 0.12;
                break;
        }
        const corePulse = 1.0 + corePulseAmt * Math.sin((t / corePulsePeriod) * Math.PI * 2);
        coreMat.size = coreSizeBase * corePulse;
        coreMat.opacity = coreOpacity;

        if (state === 'thinking') {
            mat.color.lerp(new THREE.Color(0x6ec4ff), COLOR_LERP);
            lineMat.color.lerp(new THREE.Color(0x6ec4ff), COLOR_LERP);
            coreMat.color.lerp(new THREE.Color(0xa0d8ff), COLOR_LERP);
        } else if (state === 'speaking') {
            mat.color.lerp(new THREE.Color(0x5ab8f0), COLOR_LERP);
            lineMat.color.lerp(new THREE.Color(0x5ab8f0), COLOR_LERP);
            coreMat.color.lerp(new THREE.Color(0x8dd4ff), COLOR_LERP);
        } else {
            mat.color.lerp(new THREE.Color(0x4ca8e8), COLOR_LERP);
            lineMat.color.lerp(new THREE.Color(0x4ca8e8), COLOR_LERP);
            coreMat.color.lerp(new THREE.Color(0x8dd4ff), COLOR_LERP);
        }

        // Slower, gentler camera orbit — sin/cos multipliers 0.02/0.03 → 0.01/0.015,
        // orbit radius 5/3 → 3/2.
        camera.position.x = Math.sin(t * 0.01) * 3;
        camera.position.y = Math.cos(t * 0.015) * 2;
        camera.lookAt(0, 0, cloudZ * 0.2);

        // ── Follow-up countdown ring ──
        // The ring scales with the current render radius so it always sits
        // just outside the particle cloud. Opacity target is 0.7 while the
        // window is active and we're within the final 5 s; otherwise 0.
        // The drawRange walks from full → empty over those last 5 s.
        const RING_SCALE = 1.15;
        ring.scale.setScalar(currentRadius * RING_SCALE);
        ring.position.z = cloudZ * 0.2;

        // Show the ring only inside the last 5 s of the window.
        const ringVisible = followUpActive && followUpSeconds > 0 && followUpSeconds <= 5;
        ringOpacityTarget = ringVisible ? 0.7 : 0.0;
        // Lerp at ~180 ms (at 60 fps, factor ≈ 0.09 per frame).
        ringOpacityCurrent += (ringOpacityTarget - ringOpacityCurrent) * 0.09;
        ringMat.opacity = ringOpacityCurrent;

        if (ringVisible) {
            // Fraction of segments to draw. At seconds=5 → full ring; at 0 → empty.
            const frac = Math.max(0, Math.min(1, followUpSeconds / 5));
            const segs = Math.max(1, Math.round((RING_SEGMENTS + 1) * frac));
            ringGeo.setDrawRange(0, segs);
        } else if (ringOpacityCurrent < 0.01) {
            // Fully faded — reset drawRange so a fresh arm doesn't flash mid-frame.
            ringGeo.setDrawRange(0, RING_SEGMENTS + 1);
        }

        renderer.render(scene, camera);
    }

    function onResize() {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    }

    window.addEventListener('resize', onResize);
    animate();

    return {
        setState(s: OrbState) {
            state = s;
        },
        setAnalyser(a: AnalyserNode | null) {
            analyser = a;
            if (a) freqData = new Uint8Array(a.frequencyBinCount);
        },
        setMockMode(m: OrbState | null) {
            mockMode = m;
        },
        setFollowUp(active: boolean, seconds: number) {
            followUpActive = active;
            followUpSeconds = Math.max(0, seconds);
        },
        destroy() {
            destroyed = true;
            window.removeEventListener('resize', onResize);
            glowTex.dispose();
            ringGeo.dispose();
            ringMat.dispose();
            renderer.dispose();
        },
    };
}
