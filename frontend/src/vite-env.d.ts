/// <reference types="vite/client" />

/**
 * Augment AnalyserNode to accept Uint8Array<ArrayBufferLike> in addition to
 * Uint8Array<ArrayBuffer>. TypeScript 6 introduced stricter generic variance
 * for typed arrays; the DOM lib types getByteFrequencyData as requiring
 * Uint8Array<ArrayBuffer> while new Uint8Array(n) resolves to
 * Uint8Array<ArrayBufferLike>. This merge widens the parameter to match
 * actual runtime behaviour.
 */
interface AnalyserNode {
  getByteFrequencyData(array: Uint8Array<ArrayBufferLike>): void;
  getByteTimeDomainData(array: Uint8Array<ArrayBufferLike>): void;
}
