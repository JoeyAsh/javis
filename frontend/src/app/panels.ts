/**
 * JARVIS panel registry — single source of truth for panel metadata.
 *
 * Defines which panels exist, their display metadata, and their default slot.
 * WindowHost maps this array onto WindowManager's managedWindows.
 */

import type { ComponentType } from 'react';
import type { SlotId } from '@common/types';
import type { PanelMode } from '@common/types';

import { AgendaPanel } from '@features/agenda';
import { MailPanel } from '@features/mail';
import { NotificationsPanel } from '@features/notifications';
import { TranscriptPanel } from '@features/transcript';
import { NowPlayingPanel } from '@features/nowplaying';
import { SystemPanel } from '@features/system';
import { DevPanel } from '@features/dev';
import { SelfFixPanel } from '@features/selffix';
import { GitLabPanel } from '@features/gitlab';
import { LogPanel } from '@features/log';

// ── Shared panel props ────────────────────────────────────────────────────────

export interface PanelSharedProps {
    mode: PanelMode;
}

// ── Panel spec ────────────────────────────────────────────────────────────────

export interface PanelSpec {
    id: string;
    title: string;
    /** Icon glyph rendered in the window title bar. */
    icon: string;
    homeSlot: SlotId;
    // Panels may accept additional props beyond mode; typed as the widest
    // safe intersection. Individual panels declare their own props internally.
    Component: ComponentType<PanelSharedProps>;
}

// ── Registry ──────────────────────────────────────────────────────────────────

export const PANELS: ReadonlyArray<PanelSpec> = [
    {
        id: 'agenda',
        title: 'Agenda',
        icon: '▦',
        homeSlot: 'L1',
        Component: AgendaPanel as ComponentType<PanelSharedProps>,
    },
    {
        id: 'mail',
        title: 'Inbox',
        icon: '✉',
        homeSlot: 'L2',
        Component: MailPanel as ComponentType<PanelSharedProps>,
    },
    {
        id: 'notifications',
        title: 'Proactive',
        icon: '⚡',
        homeSlot: 'L3',
        Component: NotificationsPanel as ComponentType<PanelSharedProps>,
    },
    {
        id: 'transcript',
        title: 'Transcript',
        icon: '▸',
        homeSlot: 'B1',
        Component: TranscriptPanel as ComponentType<PanelSharedProps>,
    },
    {
        id: 'nowplaying',
        title: 'Now Playing',
        icon: '♫',
        homeSlot: 'R1',
        Component: NowPlayingPanel as ComponentType<PanelSharedProps>,
    },
    {
        id: 'system',
        title: 'System',
        icon: '◈',
        homeSlot: 'R3',
        Component: SystemPanel as ComponentType<PanelSharedProps>,
    },
    {
        id: 'dev',
        title: 'Dev Toolkit',
        icon: '⚙',
        homeSlot: 'B2',
        Component: DevPanel as ComponentType<PanelSharedProps>,
    },
    {
        id: 'selffix',
        title: 'Self-Fix',
        icon: '🔧',
        homeSlot: 'B3',
        Component: SelfFixPanel as ComponentType<PanelSharedProps>,
    },
    {
        id: 'gitlab',
        title: 'GitLab',
        icon: '⬡',
        homeSlot: 'B3',
        Component: GitLabPanel as ComponentType<PanelSharedProps>,
    },
    {
        id: 'log',
        title: 'Console',
        icon: '≡',
        homeSlot: 'B3',
        Component: LogPanel as ComponentType<PanelSharedProps>,
    },
];

/** Convenience map from panel id to its home slot for WindowManager resets. */
export const DEFAULT_ASSIGNMENTS: Record<string, SlotId> = Object.fromEntries(
    PANELS.map((p) => [p.id, p.homeSlot]),
) as Record<string, SlotId>;
