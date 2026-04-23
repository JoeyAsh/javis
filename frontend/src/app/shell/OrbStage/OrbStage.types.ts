import type { AppOrbState } from '@common/types';

export interface OrbStageProps {
    orbState: AppOrbState;
    /** When true, render the Three.js orb (lazy). Defaults to CSS orb. */
    useThreeJs: boolean;
    /** When true, CSS reactor animation is suppressed (Three.js has its own). */
    reactor: boolean;
}
