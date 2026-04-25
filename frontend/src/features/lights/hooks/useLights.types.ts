import type { Zone, LightsState } from '../types';

export interface UseLightsReturn {
    zones: Zone[];
    toggle: (zoneId: string) => void;
    setBrightness: (zoneId: string, value: number) => void;
}

export interface StateWithLights {
    lights: LightsState;
}
