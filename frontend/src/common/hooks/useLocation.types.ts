import type { LocationCoords } from '@common/types/location';

export interface UseLocationReturn {
    coords: LocationCoords;
    loading: boolean;
    error: boolean;
}
