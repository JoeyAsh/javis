import type { ReactNode } from 'react';
import type { AppOrbState } from '@common/types';

export interface StatusDockProps {
    state: AppOrbState;
    onPTT?: () => void;
    ptt?: ReactNode;
    className?: string;
}
