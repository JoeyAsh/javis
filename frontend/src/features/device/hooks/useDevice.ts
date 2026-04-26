import { useAppSelector } from '@app';
import {
    selectDeviceSlug,
    selectDevicePlatform,
    selectDeviceReceived,
} from '../deviceSelectors';
import type { UseDeviceReturn } from './useDevice.types';

export type { UseDeviceReturn };

export function useDevice(): UseDeviceReturn {
    const slug = useAppSelector(selectDeviceSlug);
    const platform = useAppSelector(selectDevicePlatform);
    const received = useAppSelector(selectDeviceReceived);

    return { slug, platform, received };
}
