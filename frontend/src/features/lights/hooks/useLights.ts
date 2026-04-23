import { useCallback } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import type { AppDispatch } from '@app';
import { zoneToggled, zoneBrightnessSet } from '../lightsSlice';
import type { LightsState } from '../types';
import type { UseLightsReturn } from './useLights.types';

interface StateWithLights {
    lights: LightsState;
}

export function useLights(): UseLightsReturn {
    const dispatch = useDispatch<AppDispatch>();
    const zones = useSelector((state: StateWithLights) => state.lights.zones);

    const toggle = useCallback(
        (zoneId: string): void => {
            dispatch(zoneToggled(zoneId));
        },
        [dispatch],
    );

    const setBrightness = useCallback(
        (zoneId: string, value: number): void => {
            dispatch(zoneBrightnessSet({ zoneId, value }));
        },
        [dispatch],
    );

    return { zones, toggle, setBrightness };
}
