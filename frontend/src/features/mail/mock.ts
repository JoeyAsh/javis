import type { MailMessage } from './types';

const now = Date.now();
const ago = (min: number): string => new Date(now - min * 60_000).toISOString();

export const mailMock: MailMessage[] = [
    {
        id: 'mail-1',
        sender: 'Elena Vogt (CTO)',
        subject: 'Re: Q2 Roadmap — HUD Milestones',
        preview:
            'Looks solid. Couple of concerns on the proactive scheduler — can we sync tomorrow?',
        receivedAt: ago(8),
        isVip: true,
        unread: true,
    },
    {
        id: 'mail-2',
        sender: 'GitHub',
        subject: '[jarvis] Review requested on PR #142',
        preview: 'feature/fish-audio-rebuild — TTS buffering fixes, 6 files changed.',
        receivedAt: ago(22),
        isVip: false,
        unread: true,
    },
    {
        id: 'mail-3',
        sender: 'Marco Reinhardt',
        subject: 'Mittagessen am Donnerstag?',
        preview: 'Hey Johannes, hast du um 13:00 beim Italiener Zeit?',
        receivedAt: ago(47),
        isVip: false,
        unread: true,
    },
];
