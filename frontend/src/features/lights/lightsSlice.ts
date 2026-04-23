import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import { MOCK_ZONES } from './mock';
import type { LightsState } from './types';

const initialState: LightsState = {
    zones: MOCK_ZONES,
};

export const lightsSlice = createSlice({
    name: 'lights',
    initialState,
    reducers: {
        zoneToggled(state, action: PayloadAction<string>) {
            const zone = state.zones.find((z) => z.id === action.payload);
            if (zone === undefined) return;
            zone.on = !zone.on;
            zone.brightness = zone.on ? 60 : 0;
        },
        zoneBrightnessSet(state, action: PayloadAction<{ zoneId: string; value: number }>) {
            const zone = state.zones.find((z) => z.id === action.payload.zoneId);
            if (zone === undefined) return;
            zone.brightness = action.payload.value;
            zone.on = action.payload.value > 0;
        },
    },
});

export const { zoneToggled, zoneBrightnessSet } = lightsSlice.actions;
export default lightsSlice.reducer;
