import type { TranscriptTurn } from './types';

const now = Date.now();
const ago = (s: number): string => new Date(now - s * 1000).toISOString();

export const transcriptMock: TranscriptTurn[] = [
    {
        id: 'tr-1',
        role: 'user',
        text: 'JARVIS, what is on my calendar today?',
        at: ago(420),
    },
    {
        id: 'tr-2',
        role: 'jarvis',
        text: 'You have the platform standup in ten minutes, Sir, followed by the HUD design review at eleven-fifteen, and lunch with Sarah at half past one.',
        at: ago(412),
        salutation: 'Sir',
    },
    {
        id: 'tr-3',
        role: 'user',
        text: 'Dim the lights for focus mode.',
        at: ago(180),
    },
    {
        id: 'tr-4',
        role: 'jarvis',
        text: 'Switching to Focus scene now, Johannes. Desk strip at seventy percent, ceiling hex at forty-five. Ambient nominal.',
        at: ago(176),
        salutation: 'Johannes',
    },
];
