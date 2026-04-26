import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import type { DeviceInfoPayload, DeviceState } from './types';

const initialState: DeviceState = {
    slug: '',
    platform: '',
    hostname: '',
    received: false,
};

const deviceSlice = createSlice({
    name: 'device',
    initialState,
    reducers: {
        deviceInfoReceived(state, action: PayloadAction<DeviceInfoPayload>) {
            state.slug = action.payload.slug;
            state.platform = action.payload.platform;
            state.hostname = action.payload.hostname;
            state.received = true;
        },
    },
});

export const { deviceInfoReceived } = deviceSlice.actions;
export type { DeviceState };
export default deviceSlice.reducer;
