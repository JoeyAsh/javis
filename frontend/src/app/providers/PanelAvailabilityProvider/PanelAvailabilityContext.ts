import { createContext } from 'react';
import type { PanelAvailabilityContextValue } from './PanelAvailabilityProvider.types';

export const PanelAvailabilityContext = createContext<PanelAvailabilityContextValue | null>(null);
