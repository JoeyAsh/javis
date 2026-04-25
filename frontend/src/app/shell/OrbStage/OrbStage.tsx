/**
 * OrbStage — selects and renders the correct orb based on settings.orbStyle.
 *
 * ThreeOrb is lazy-imported to keep the main bundle small (~150-180 KB).
 * The Three.js chunk (~511 KB) only loads when orbStyle === 'threejs'.
 * CssOrb is the eager fallback (and the Suspense boundary fallback).
 *
 * The follow_up → listening visual remap is handled in selectAppOrbState
 * (orbStateSelectors.ts) — this component receives the already-mapped state
 * from AppShell via props.
 */

import { lazy, Suspense, type ReactElement } from 'react';
import { CssOrb } from '@ui';
import type { OrbStageProps } from './OrbStage.types';

const ThreeOrb = lazy(() => import('@ui/orb/ThreeOrb'));

export function OrbStage({ orbState, useThreeJs }: OrbStageProps): ReactElement {
    if (useThreeJs) {
        return (
            <Suspense key="three" fallback={<CssOrb state={orbState} />}>
                <ThreeOrb state={orbState} />
            </Suspense>
        );
    }
    return <CssOrb key="css" state={orbState} />;
}

export default OrbStage;
