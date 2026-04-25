import type { AppOrbState } from '@common/types';

export interface CssOrbProps {
    state: AppOrbState;
    /** @default true */
    rings?: boolean;
    particles?: boolean;
    className?: string;
}

export interface ParticleConfig {
    radius: number;
    dir: 1 | -1;
    period: number;
    phase: number;
    size: number;
    colorVar: string;
}
