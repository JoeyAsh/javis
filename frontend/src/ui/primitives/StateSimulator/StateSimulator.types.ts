import type { AppOrbState } from '@common/types';

export interface StateSimulatorProps {
    state: AppOrbState;
    onChange: (state: AppOrbState) => void;
    label?: string;
    position?: 'fixed-top' | 'inline';
    className?: string;
}
