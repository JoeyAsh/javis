/**
 * PanelAvailabilityContext — lightweight registry that panels use to report
 * whether their backend data source is reachable.
 *
 * Flow:
 *  1. Each panel calls `usePanelAvailable(id, available)` after its own
 *     10-second availability timeout resolves.
 *  2. HudWindows reads `useAvailabilityMap()` and skips rendering windows
 *     whose panel has reported `available: false`.
 *
 * Default state: all panels are `true` (available) until explicitly reported
 * otherwise — panels that have no async backend (System, Transcript, Dev, Log,
 * SelfFix) never call `usePanelAvailable` and remain visible always.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import type { ReactElement, ReactNode } from 'react';
import type { PanelId } from '../../types';

type AvailabilityMap = Partial<Record<PanelId, boolean>>;

interface PanelAvailabilityValue {
  availability: AvailabilityMap;
  report: (id: PanelId, available: boolean) => void;
}

const PanelAvailabilityContext = createContext<PanelAvailabilityValue | null>(null);

export interface PanelAvailabilityProviderProps {
  children: ReactNode;
}

export function PanelAvailabilityProvider({
  children,
}: PanelAvailabilityProviderProps): ReactElement {
  const [availability, setAvailability] = useState<AvailabilityMap>({});

  const report = useCallback((id: PanelId, available: boolean): void => {
    setAvailability((prev) => {
      if (prev[id] === available) return prev;
      return { ...prev, [id]: available };
    });
  }, []);

  const value = useMemo<PanelAvailabilityValue>(
    () => ({ availability, report }),
    [availability, report],
  );

  return (
    <PanelAvailabilityContext.Provider value={value}>
      {children}
    </PanelAvailabilityContext.Provider>
  );
}

function usePanelAvailabilityContext(): PanelAvailabilityValue {
  const ctx = useContext(PanelAvailabilityContext);
  if (!ctx) {
    throw new Error('usePanelAvailable must be used inside <PanelAvailabilityProvider>');
  }
  return ctx;
}

/**
 * Called by panels that have async backends. Reports availability after the
 * 10-second timeout resolves. Uses an effect so state updates are batched
 * correctly and never happen during render.
 */
export function usePanelAvailable(id: PanelId, available: boolean): void {
  const { report } = usePanelAvailabilityContext();

  useEffect(() => {
    report(id, available);
  }, [id, available, report]);
}

/**
 * Returns the full availability map. Used by HudWindows to filter panels.
 * A panel with no entry defaults to `true` (available).
 */
export function useAvailabilityMap(): AvailabilityMap {
  const { availability } = usePanelAvailabilityContext();
  return availability;
}

export function isPanelAvailable(map: AvailabilityMap, id: PanelId): boolean {
  const v = map[id];
  return v === undefined || v === true;
}
