export { DeviceBadge } from './components/DeviceBadge';
export type { DeviceBadgeProps } from './components/DeviceBadge';

export { useDevice } from './hooks/useDevice';
export type { UseDeviceReturn } from './hooks/useDevice';

export { deviceApi, useStreamDeviceInfoQuery } from './deviceApi';
export { deviceInfoReceived } from './deviceSlice';
export type { DeviceState } from './deviceSlice';
export {
    selectDeviceSlug,
    selectDevicePlatform,
    selectDeviceReceived,
} from './deviceSelectors';
export type { DeviceInfoPayload } from './types';
