import type { ReactNode } from 'react';
import type { PanelId } from '@common/types';

export type AvailabilityMap = Partial<Record<PanelId, boolean>>;

export interface PanelAvailabilityContextValue {
    availability: AvailabilityMap;
    report: (id: PanelId, available: boolean) => void;
}

export interface PanelAvailabilityProviderProps {
    children: ReactNode;
}
