import * as THREE from 'three';
import type { OrbState } from '../types';

/**
 * Three.js particle orb engine for JARVIS visualization.
 */
export class Orb {
  private renderer: THREE.WebGLRenderer;
  private scene: THREE.Scene;
  private camera: THREE.PerspectiveCamera;
  private particles: THREE.Points;
  private geometry: THREE.BufferGeometry;
  private material: THREE.PointsMaterial;
  private positions: Float32Array;
  private originalPositions: Float32Array;
  private velocities: Float32Array;
  private animationId: number | null = null;
  private state: OrbState = 'idle';
  private analyser: AnalyserNode | null = null;
  private analyserData: Uint8Array | null = null;
  private time: number = 0;
  private pulsePhase: number = 0;
  private rotationSpeed: number = 0;

  // Color definitions
  private static readonly COLORS: Record<OrbState, number> = {
    idle: 0x4ca8e8,
    listening: 0x4ca8e8,
    thinking: 0x6ec4ff,
    speaking: 0x5ab8f0,
  };

  private static readonly PARTICLE_COUNT = 2000;
  private static readonly SPHERE_RADIUS = 2;

  constructor(canvas: HTMLCanvasElement) {
    // Initialize renderer
    this.renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: true,
    });
    this.renderer.setSize(window.innerWidth, window.innerHeight);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    // Initialize scene
    this.scene = new THREE.Scene();

    // Initialize camera
    this.camera = new THREE.PerspectiveCamera(
      75,
      window.innerWidth / window.innerHeight,
      0.1,
      1000
    );
    this.camera.position.z = 5;

    // Create particle geometry
    this.geometry = new THREE.BufferGeometry();
    this.positions = new Float32Array(Orb.PARTICLE_COUNT * 3);
    this.originalPositions = new Float32Array(Orb.PARTICLE_COUNT * 3);
    this.velocities = new Float32Array(Orb.PARTICLE_COUNT * 3);

    // Distribute particles on a sphere
    for (let i = 0; i < Orb.PARTICLE_COUNT; i++) {
      const phi = Math.acos(2 * Math.random() - 1);
      const theta = Math.random() * Math.PI * 2;

      const x = Orb.SPHERE_RADIUS * Math.sin(phi) * Math.cos(theta);
      const y = Orb.SPHERE_RADIUS * Math.sin(phi) * Math.sin(theta);
      const z = Orb.SPHERE_RADIUS * Math.cos(phi);

      this.positions[i * 3] = x;
      this.positions[i * 3 + 1] = y;
      this.positions[i * 3 + 2] = z;

      this.originalPositions[i * 3] = x;
      this.originalPositions[i * 3 + 1] = y;
      this.originalPositions[i * 3 + 2] = z;

      // Random velocities for noise movement
      this.velocities[i * 3] = (Math.random() - 0.5) * 0.02;
      this.velocities[i * 3 + 1] = (Math.random() - 0.5) * 0.02;
      this.velocities[i * 3 + 2] = (Math.random() - 0.5) * 0.02;
    }

    this.geometry.setAttribute(
      'position',
      new THREE.BufferAttribute(this.positions, 3)
    );

    // Create particle material
    this.material = new THREE.PointsMaterial({
      color: Orb.COLORS.idle,
      size: 0.03,
      transparent: true,
      opacity: 0.8,
      blending: THREE.AdditiveBlending,
    });

    // Create particles mesh
    this.particles = new THREE.Points(this.geometry, this.material);
    this.scene.add(this.particles);

    // Handle resize
    window.addEventListener('resize', this.handleResize);

    // Start animation loop
    this.animate();
  }

  private handleResize = (): void => {
    this.camera.aspect = window.innerWidth / window.innerHeight;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(window.innerWidth, window.innerHeight);
  };

  /**
   * Set the current orb state.
   */
  setState(state: OrbState): void {
    this.state = state;
    this.material.color.setHex(Orb.COLORS[state]);

    // Adjust animation parameters based on state
    switch (state) {
      case 'idle':
        this.rotationSpeed = 0.001;
        break;
      case 'listening':
        this.rotationSpeed = 0.002;
        this.pulsePhase = 0;
        break;
      case 'thinking':
        this.rotationSpeed = 0.015;
        break;
      case 'speaking':
        this.rotationSpeed = 0.003;
        break;
    }
  }

  /**
   * Set the audio analyser for speaking animation.
   */
  setAnalyser(analyser: AnalyserNode | null): void {
    this.analyser = analyser;
    if (analyser) {
      this.analyserData = new Uint8Array(analyser.frequencyBinCount);
    } else {
      this.analyserData = null;
    }
  }

  /**
   * Animation loop.
   */
  private animate = (): void => {
    this.animationId = requestAnimationFrame(this.animate);
    this.time += 0.016; // Approximate 60fps delta

    // Update particle positions based on state
    this.updateParticles();

    // Rotate the entire particle system
    this.particles.rotation.y += this.rotationSpeed;
    this.particles.rotation.x = Math.sin(this.time * 0.5) * 0.1;

    // Update geometry
    this.geometry.attributes.position.needsUpdate = true;

    // Render
    this.renderer.render(this.scene, this.camera);
  };

  private updateParticles(): void {
    const positionAttr = this.geometry.attributes.position;
    const positions = positionAttr.array as Float32Array;

    // Get audio data if available
    let audioLevel = 0;
    if (this.analyser && this.analyserData && this.state === 'speaking') {
      this.analyser.getByteFrequencyData(this.analyserData);
      audioLevel =
        this.analyserData.reduce((a, b) => a + b, 0) /
        this.analyserData.length /
        255;
    }

    for (let i = 0; i < Orb.PARTICLE_COUNT; i++) {
      const i3 = i * 3;

      // Get original position
      const ox = this.originalPositions[i3];
      const oy = this.originalPositions[i3 + 1];
      const oz = this.originalPositions[i3 + 2];

      // Calculate displacement based on state
      let dx = 0,
        dy = 0,
        dz = 0;

      switch (this.state) {
        case 'idle': {
          // Gentle noise movement
          const noiseScale = 0.1;
          dx = Math.sin(this.time + i * 0.1) * noiseScale;
          dy = Math.cos(this.time * 0.8 + i * 0.15) * noiseScale;
          dz = Math.sin(this.time * 0.6 + i * 0.12) * noiseScale;
          break;
        }

        case 'listening': {
          // Pulse ring effect
          this.pulsePhase += 0.003;
          const pulse = Math.sin(this.pulsePhase) * 0.3 + 1;
          const scale = 1 + (pulse - 1) * 0.2;
          dx = ox * (scale - 1);
          dy = oy * (scale - 1);
          dz = oz * (scale - 1);
          break;
        }

        case 'thinking': {
          // Spiral spinning effect
          const angle = this.time * 2 + i * 0.01;
          const spiralRadius = 0.15;
          dx = Math.cos(angle) * spiralRadius;
          dy = Math.sin(angle * 0.5) * spiralRadius;
          dz = Math.sin(angle) * spiralRadius;
          break;
        }

        case 'speaking': {
          // Wave animation driven by audio
          const waveFreq = 3;
          const waveAmp = 0.3 * (0.5 + audioLevel * 2);
          const phase = Math.atan2(oy, ox);
          const wave = Math.sin(phase * waveFreq + this.time * 4) * waveAmp;
          const direction = Math.sqrt(ox * ox + oy * oy + oz * oz);
          if (direction > 0) {
            dx = (ox / direction) * wave;
            dy = (oy / direction) * wave;
            dz = (oz / direction) * wave;
          }
          break;
        }
      }

      // Apply displacement
      positions[i3] = ox + dx;
      positions[i3 + 1] = oy + dy;
      positions[i3 + 2] = oz + dz;
    }
  }

  /**
   * Clean up resources.
   */
  destroy(): void {
    if (this.animationId !== null) {
      cancelAnimationFrame(this.animationId);
    }

    window.removeEventListener('resize', this.handleResize);

    this.geometry.dispose();
    this.material.dispose();
    this.renderer.dispose();
  }
}
