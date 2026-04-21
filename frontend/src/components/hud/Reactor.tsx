/**
 * Reactor — standalone 900×900 px radial halo positioned behind the orb.
 *
 * Must be mounted between <Scene /> and the orb element in App.tsx so it
 * renders at z-index 0 (behind everything).  The equivalent inline reactor
 * div was removed from Scene.tsx.
 */

import type { ReactElement } from 'react';
import './Reactor.css';

export function Reactor(): ReactElement {
  return <div className="reactor" aria-hidden />;
}

export default Reactor;
