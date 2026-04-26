import type { DeviceInfoPayload, DeviceState } from './types';

export const deviceInfoPayloadMock: DeviceInfoPayload = {
    slug: 'laptop-paps',
    platform: 'linux',
    hostname: 'paps-laptop',
};

export const deviceStateMock: DeviceState = {
    slug: 'laptop-paps',
    platform: 'linux',
    hostname: 'paps-laptop',
    received: true,
};

export const deviceStateInitialMock: DeviceState = {
    slug: '',
    platform: '',
    hostname: '',
    received: false,
};
