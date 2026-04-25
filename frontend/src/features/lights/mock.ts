/**
 * Lights feature mock data — 4 zones matching the Hypermodern HUD prototype.
 * Replaced by live Home Assistant data in backend follow-up #54.
 */
import type { Zone } from './types';

export const MOCK_ZONES: Zone[] = [
    { id: 'lr', label: 'Living Room', on: true, brightness: 72 },
    { id: 'kt', label: 'Kitchen', on: true, brightness: 45 },
    { id: 'wk', label: 'Workshop', on: false, brightness: 0 },
    { id: 'bd', label: 'Bedroom', on: false, brightness: 0 },
];
