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

export function createOrb(canvas: HTMLCanvasElement): Orb {
  let destroyed = false;
  const N = 2000;

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setClearColor(0x050508, 1);

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

  for (let i = 0; i < N; i++) {
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    const r = Math.pow(Math.random(), 0.5) * 25;
    pos[i * 3] = r * Math.sin(phi) * Math.cos(theta);
    pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
    pos[i * 3 + 2] = r * Math.cos(phi);
    phase[i] = Math.random() * 1000;
    brightness[i] = 0.7 + Math.random() * 0.3; // range [0.7, 1.0]
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
    color: 0x4ca8e8, transparent: true, opacity: 0.0,
    blending: THREE.AdditiveBlending, depthWrite: false,
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
    color: 0xffffff, size: 0.8, transparent: true, opacity: 1.0,
    sizeAttenuation: true, blending: THREE.AdditiveBlending, depthWrite: false,
    map: glowTex, alphaTest: 0.001,
  });

  const electronsMesh = new THREE.Points(electronGeo, electronMat);
  scene.add(electronsMesh);

  interface ElectronData {
    sx: number; sy: number; sz: number;
    ex: number; ey: number; ez: number;
    t: number; speed: number;
  }
  const activeElectrons: ElectronData[] = [];
  let electronSpawnRate = 0;
  let targetElectronRate = 0;
  let lastElectronSpawn = 0;

  let activeConnections: { x1: number; y1: number; z1: number; x2: number; y2: number; z2: number }[] = [];

  // ── State ──
  let state: OrbState = 'idle';
  let targetRadius = 25, currentRadius = 25;
  let targetSpeed = 0.3, currentSpeed = 0.3;
  let targetBright = 0.6, currentBright = 0.6;
  let targetSize = 0.6, currentSize = 0.6;
  let lineAmount = 0, targetLineAmount = 0;
  /** Smoothly lerped line opacity — avoids hard jumps when lineAmount changes. */
  let currentLineOpacity = 0;
  const lineDistance = 8;

  let spinX = 0, spinY = 0, spinZ = 0;
  let transitionEnergy = 0;
  let lastState: OrbState = 'idle';

  let cloudZ = 0, cloudZVel = 0;

  // ── Audio ──
  let analyser: AnalyserNode | null = null;
  let freqData = new Uint8Array(64);
  let bass = 0, mid = 0;

  const clock = new THREE.Clock();

  // Lerp rate constants — centralised for easy tweaking.
  const LERP_RATE = 0.012;
  const COLOR_LERP = 0.008;

  function animate() {
    if (destroyed) return;
    requestAnimationFrame(animate);
    const t = clock.getElapsedTime();

    switch (state) {
      case 'idle':
        targetRadius = 28; targetSpeed = 0.2; targetBright = 0.5; targetSize = 0.55;
        targetLineAmount = 0.15; targetElectronRate = 0; break;
      case 'listening':
        targetRadius = 22; targetSpeed = 0.3; targetBright = 0.65; targetSize = 0.6;
        targetLineAmount = 0.4; targetElectronRate = 0; break;
      case 'thinking':
        targetRadius = 16; targetSpeed = 0.5; targetBright = 0.7; targetSize = 0.5;
        targetLineAmount = 1.0; targetElectronRate = 0.015; break;
      case 'speaking':
        targetRadius = 18; targetSpeed = 0.2; targetBright = 0.7; targetSize = 0.6;
        targetLineAmount = 0.8; targetElectronRate = 0; break;
    }

    currentRadius += (targetRadius - currentRadius) * LERP_RATE;
    currentSpeed += (targetSpeed - currentSpeed) * LERP_RATE;
    currentBright += (targetBright - currentBright) * LERP_RATE;
    currentSize += (targetSize - currentSize) * LERP_RATE;
    lineAmount += (targetLineAmount - lineAmount) * LERP_RATE;
    electronSpawnRate += (targetElectronRate - electronSpawnRate) * LERP_RATE;

    // Smooth line opacity — lerps independently at a slower rate than other params.
    currentLineOpacity += (lineAmount * 0.18 - currentLineOpacity) * 0.01;

    if (state !== lastState) { transitionEnergy = 1.0; lastState = state; }
    // Faster decay (0.975) + 40% reduced forces → smooth rather than jerky transitions.
    transitionEnergy *= 0.975;
    if (transitionEnergy > 0.05) {
      spinX += transitionEnergy * 0.007 * Math.sin(t * 1.7);
      spinY += transitionEnergy * 0.009;
      spinZ += transitionEnergy * 0.005 * Math.cos(t * 1.3);
    }

    // Audio
    bass = 0; mid = 0;
    if (analyser) {
      analyser.getByteFrequencyData(freqData);
      let bSum = 0, mSum = 0;
      for (let i = 0; i < 8; i++) bSum += freqData[i];
      for (let i = 8; i < 24; i++) mSum += freqData[i];
      bass = bSum / (8 * 255); mid = mSum / (16 * 255);
    }

    // Depth Z breathing — increased spring damping (0.96) and reduced force (0.005).
    let zTarget = Math.sin(t * 0.12) * 8;
    if (state === 'thinking') zTarget = Math.sin(t * 0.3) * 15 + Math.sin(t * 0.9) * 6;
    else if (state === 'speaking') zTarget = Math.sin(t * 0.15) * 6 - bass * 10;
    cloudZVel += (zTarget - cloudZ) * 0.005;
    cloudZVel *= 0.96;
    cloudZ += cloudZVel;

    const syncTransform = (obj: THREE.Object3D) => {
      obj.rotation.x = spinX; obj.rotation.y = spinY; obj.rotation.z = spinZ;
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

    for (let i = 0; i < N; i++) {
      const i3 = i * 3;
      const x = a[i3], y = a[i3 + 1], z = a[i3 + 2];
      const px = phase[i];

      // Noise forces reduced ~30% (0.001 → 0.0007, 0.0008 → 0.00056).
      vel[i3]     += Math.sin(t * 0.05 + px) * 0.0007 * currentSpeed;
      vel[i3 + 1] += Math.cos(t * 0.06 + px * 1.3) * 0.0007 * currentSpeed;
      vel[i3 + 2] += Math.sin(t * 0.055 + px * 0.7) * 0.0007 * currentSpeed;
      vel[i3]     += Math.sin(t * 0.02 + px * 2.1 + y * 0.1) * 0.00056 * currentSpeed;
      vel[i3 + 1] += Math.cos(t * 0.025 + px * 1.7 + z * 0.1) * 0.00056 * currentSpeed;
      vel[i3 + 2] += Math.sin(t * 0.022 + px * 0.9 + x * 0.1) * 0.00056 * currentSpeed;

      const dist = Math.sqrt(x * x + y * y + z * z) || 0.01;
      const pull = Math.max(0, dist - currentRadius) * 0.002 + 0.0003;
      vel[i3] -= (x / dist) * pull;
      vel[i3 + 1] -= (y / dist) * pull;
      vel[i3 + 2] -= (z / dist) * pull;

      if (bass > 0.05) {
        vel[i3]     += (x / dist) * bass * 0.02;
        vel[i3 + 1] += (y / dist) * bass * 0.02;
        vel[i3 + 2] += (z / dist) * bass * 0.02;
      }
      if (state === 'speaking' && mid > 0.1) {
        const pulse = Math.sin(t * 8 + px);
        vel[i3]     += (x / dist) * mid * 0.012 * pulse;
        vel[i3 + 1] += (y / dist) * mid * 0.012 * pulse;
      }

      // Reduced damping: 0.992 → 0.985 (particles glide more, less jittery).
      vel[i3] *= 0.985; vel[i3 + 1] *= 0.985; vel[i3 + 2] *= 0.985;
      a[i3] += vel[i3]; a[i3 + 1] += vel[i3 + 1]; a[i3 + 2] += vel[i3 + 2];
    }
    p.needsUpdate = true;

    // ── Update lines ──
    if (lineAmount > 0.01) {
      const lp = lineGeo.getAttribute('position') as THREE.BufferAttribute;
      const la = lp.array as Float32Array;
      let lineCount = 0;
      const maxDist = lineDistance * (1 + bass * 0.5);
      const maxDistSq = maxDist * maxDist;
      const step = Math.max(1, Math.floor(N / 600));

      for (let i = 0; i < N && lineCount < MAX_LINES; i += step) {
        const i3 = i * 3;
        const x1 = a[i3], y1 = a[i3 + 1], z1 = a[i3 + 2];
        for (let j = i + step; j < N && lineCount < MAX_LINES; j += step) {
          const j3 = j * 3;
          const dx = a[j3] - x1, dy = a[j3 + 1] - y1, dz = a[j3 + 2] - z1;
          if (dx * dx + dy * dy + dz * dz < maxDistSq) {
            const idx = lineCount * 6;
            la[idx] = x1; la[idx+1] = y1; la[idx+2] = z1;
            la[idx+3] = a[j3]; la[idx+4] = a[j3+1]; la[idx+5] = a[j3+2];
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
          x1: la[ci], y1: la[ci+1], z1: la[ci+2],
          x2: la[ci+3], y2: la[ci+4], z2: la[ci+5],
        });
      }
    } else {
      lineGeo.setDrawRange(0, 0);
      activeConnections = [];
    }

    // ── Update electrons ──
    if (activeConnections.length > 0 && electronSpawnRate > 0.005) {
      if (activeElectrons.length < 3 && (t - lastElectronSpawn) > 1.0) {
        const conn = activeConnections[Math.floor(Math.random() * activeConnections.length)];
        activeElectrons.push({
          sx: conn.x1, sy: conn.y1, sz: conn.z1,
          ex: conn.x2, ey: conn.y2, ez: conn.z2,
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
    const baseOpacity = currentBright + bass * 0.08;
    // Shimmer: blend base opacity with a per-frame average of brightness offsets
    let shimmerSum = 0;
    for (let i = 0; i < N; i++) {
      shimmerSum += brightness[i] * (0.85 + 0.15 * Math.sin(t * 0.7 + phase[i] * 0.05));
    }
    const shimmerAvg = shimmerSum / N; // stays close to ~0.87
    // Apply idle breathing pulse to opacity and size.
    mat.opacity = baseOpacity * shimmerAvg * idleBreath;
    mat.size = (currentSize + bass * 0.05) * idleBreath;

    // ── Core particles heartbeat pulse ~~
    // Slow sine (period 3 s) modulates core size ±15%.
    const corePulse = 1.0 + 0.15 * Math.sin((t / 3.0) * Math.PI * 2);
    coreMat.size = 1.2 * corePulse;

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
    setState(s: OrbState) { state = s; },
    setAnalyser(a: AnalyserNode | null) {
      analyser = a;
      if (a) freqData = new Uint8Array(a.frequencyBinCount);
    },
    destroy() {
      destroyed = true;
      window.removeEventListener('resize', onResize);
      glowTex.dispose();
      renderer.dispose();
    },
  };
}
