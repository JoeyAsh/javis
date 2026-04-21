import type { AgendaEvent } from '../types';

const now = new Date();
const iso = (addMin: number): string => new Date(now.getTime() + addMin * 60_000).toISOString();

export const agendaMock: AgendaEvent[] = [
    {
        id: 'evt-1',
        title: 'Standup — Platform Team',
        start: iso(10),
        end: iso(25),
        location: 'Zoom',
        calendar: 'Work',
        minutesToNext: 10,
    },
    {
        id: 'evt-2',
        title: 'Design-Review JARVIS HUD',
        start: iso(75),
        end: iso(135),
        location: 'Konferenzraum Orion',
        calendar: 'Work',
        minutesToNext: 50,
    },
    {
        id: 'evt-3',
        title: 'Lunch with Sarah',
        start: iso(180),
        end: iso(240),
        location: 'Café Lichtblick',
        calendar: 'Personal',
        minutesToNext: 45,
    },
    {
        id: 'evt-4',
        title: 'Refactor-Deep-Dive (Solo)',
        start: iso(300),
        end: iso(420),
        calendar: 'Focus',
        minutesToNext: 60,
    },
];
