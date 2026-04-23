import { useGetLocationQuery } from '@core/api/locationApi';
import type { LocationCoords } from '@common/types/location';
import type { UseLocationReturn } from './useLocation.types';

const FALLBACK: LocationCoords = { latitude: 52.52, longitude: 13.41 };

/**
 * Fetches the configured location from the backend.
 * Falls back to Berlin when the request is pending or fails.
 */
export function useLocation(): UseLocationReturn {
    const { data, isLoading, isError } = useGetLocationQuery();
    return {
        coords: data ?? FALLBACK,
        loading: isLoading,
        error: isError,
    };
}

export default useLocation;
