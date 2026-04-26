import { createSelector } from '@reduxjs/toolkit';
import type { RootState } from '@app';

const selectDeviceState = (state: RootState) => state.device;

export const selectDeviceSlug = createSelector(
    selectDeviceState,
    (device) => device.slug,
);

export const selectDevicePlatform = createSelector(
    selectDeviceState,
    (device) => device.platform,
);

export const selectDeviceReceived = createSelector(
    selectDeviceState,
    (device) => device.received,
);
