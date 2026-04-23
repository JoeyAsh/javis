import type { Zone } from '../types';

export interface UseLightsReturn {
    zones: Zone[];
    toggle: (zoneId: string) => void;
    setBrightness: (zoneId: string, value: number) => void;
}
