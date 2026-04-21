/**
 * copy-sounds.mjs
 *
 * Idempotently copies ../assets/sounds/ → ./public/sounds/ before dev/build.
 * If the source directory does not exist, logs a warning and exits cleanly —
 * the audio engine handles missing files at runtime with graceful 404 handling.
 */

import { cpSync, existsSync, mkdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));

const src = resolve(__dirname, '../../assets/sounds');
const dest = resolve(__dirname, '../public/sounds');

if (!existsSync(src)) {
  console.warn('[copy-sounds] WARNING: Source directory not found:', src);
  console.warn('[copy-sounds] Skipping sound copy. SFX will be unavailable.');
  process.exit(0);
}

mkdirSync(dest, { recursive: true });

cpSync(src, dest, { recursive: true });

console.log('[copy-sounds] Copied', src, '→', dest);
