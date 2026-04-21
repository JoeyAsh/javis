/**
 * useLocation — fetches geographic coordinates from the JARVIS backend.
 *
 * Hits `GET http://localhost:8766/api/config/location` which returns
 * `{ latitude: number; longitude: number }` read from config.yaml.
 *
 * Falls back to Berlin (52.52, 13.41) when the backend is unreachable so
 * the weather widget still shows data in browser-only mode.
 */

import { useEffect, useState } from 'react';

export interface LocationCoords {
  latitude: number;
  longitude: number;
}

interface LocationState {
  coords: LocationCoords;
  /** True while the first fetch is pending. */
  loading: boolean;
  /** True if the backend returned an error or was unreachable. */
  error: boolean;
}

/** Berlin fallback — user changes config.yaml; frontend picks it up on next load. */
const FALLBACK: LocationCoords = { latitude: 52.52, longitude: 13.41 };

interface LocationApiResponse {
  latitude: number;
  longitude: number;
}

/**
 * Fetches location coordinates from the backend config endpoint.
 * Resolves immediately from the fallback if the fetch fails so callers
 * always have a usable `coords` value.
 */
export function useLocation(): LocationState {
  const [state, setState] = useState<LocationState>({
    coords: FALLBACK,
    loading: true,
    error: false,
  });

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();

    async function fetchLocation(): Promise<void> {
      try {
        const res = await fetch('http://localhost:8766/api/config/location', {
          signal: controller.signal,
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = (await res.json()) as LocationApiResponse;
        if (!cancelled) {
          setState({
            coords: { latitude: data.latitude, longitude: data.longitude },
            loading: false,
            error: false,
          });
        }
      } catch {
        if (!cancelled) {
          setState({ coords: FALLBACK, loading: false, error: true });
        }
      }
    }

    void fetchLocation();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, []);

  return state;
}

export default useLocation;
