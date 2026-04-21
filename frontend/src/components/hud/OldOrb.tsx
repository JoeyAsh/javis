/**
 * OldOrb — thin wrapper around the existing Three.js OrbCanvas.
 *
 * Exposes the same prop surface as the Hypermodern Orb so App.tsx can
 * swap between variants without branching on the call site.
 *
 * Notes:
 * - `state: 'working'` is mapped to `'thinking'` for OrbCanvas (same as before).
 * - `rings` and `particles` props are accepted but ignored — the classic orb
 *   has its own Three.js aesthetic and is not decomposed.
 * - `analyser` and `mockMode` are not exposed here; App.tsx passes them
 *   directly when rendering OrbCanvas itself. OldOrb is only used in the
 *   variant-swap path.
 */

import type { ReactElement } from 'react';
import { OrbCanvas } from '../OrbCanvas';
import { OrbErrorBoundary } from '../OrbErrorBoundary';
import type { AppOrbState } from '../../types';

export interface OldOrbProps {
  state: AppOrbState;
  /** Accepted for interface parity with Orb; ignored. */
  rings?: boolean;
  /** Accepted for interface parity with Orb; ignored. */
  particles?: boolean;
  analyser?: AnalyserNode | null;
  mockMode?: AppOrbState | null;
  followUp?: { active: boolean; secondsRemaining: number };
}

/**
 * Classic Three.js orb, wrapped for swappability with the Hypermodern CSS orb.
 */
export function OldOrb({
  state,
  rings: _rings,
  particles: _particles,
  analyser = null,
  mockMode = null,
  followUp,
}: OldOrbProps): ReactElement {
  return (
    <OrbErrorBoundary>
      <OrbCanvas
        orbState={state}
        analyser={analyser}
        mockMode={mockMode}
        followUp={followUp}
      />
    </OrbErrorBoundary>
  );
}

export default OldOrb;
