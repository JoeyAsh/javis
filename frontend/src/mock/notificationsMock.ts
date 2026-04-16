import type { HudNotification } from '../types';

const now = Date.now();

export const notificationsMock: HudNotification[] = [
  {
    id: 'nt-1',
    severity: 'warning',
    title: 'Meeting in 10 Minutes',
    detail: 'Standup — Platform Team (Zoom). Shall I pull up the notes, Sir?',
    timestamp: new Date(now - 30_000).toISOString(),
  },
  {
    id: 'nt-2',
    severity: 'urgent',
    title: 'VIP mail from Elena Vogt',
    detail: 'Subject: "Q2 Roadmap — HUD Milestones". Marked VIP, Johannes.',
    timestamp: new Date(now - 8 * 60_000).toISOString(),
  },
  {
    id: 'nt-3',
    severity: 'info',
    title: 'Uncommitted changes for 2h',
    detail: 'jarvis (feature/fish-audio-rebuild) — 12 files dirty. Committing advised.',
    timestamp: new Date(now - 2 * 3600_000).toISOString(),
  },
];
