import type { AppOrbState } from '@common/types';

export interface CssOrbProps {
    state: AppOrbState;
    /** @default true */
    rings?: boolean;
    particles?: boolean;
    className?: string;
}
