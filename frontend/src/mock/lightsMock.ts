import type { LightsState } from '../types';

export const lightsMock: LightsState = {
    devices: [
        { id: 'gv-1', name: 'Desk Strip', on: true, brightness: 70, color: '#4ca8e8' },
        { id: 'gv-2', name: 'Ceiling Hex', on: true, brightness: 45, color: '#ff8c42' },
        { id: 'gv-3', name: 'Floor Lamp', on: false, brightness: 30, color: '#a86cff' },
    ],
    activeScene: 'Focus',
};
