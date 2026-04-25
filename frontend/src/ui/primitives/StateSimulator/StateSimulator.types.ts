import type { AppOrbState } from '@common/types';

export interface StateSimulatorProps {
    state: AppOrbState;
    onChange: (state: AppOrbState) => void;
    label?: string;
    position?: 'fixed-top' | 'inline';
    className?: string;
}

export interface SimOption {
    key: AppOrbState;
    label: string;
}

export interface SimButtonProps {
    option: SimOption;
    active: boolean;
    onChange: (state: AppOrbState) => void;
}
