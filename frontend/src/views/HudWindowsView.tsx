/**
 * HudWindowsView — renders all JARVIS panels inside the lib WindowManager.
 *
 * Replaces legacy components/hud/HudWindows.tsx. Uses lib WindowManager
 * composition (controlled assignments + uncontrolled modes/expandedRects).
 * Filters panels by PanelAvailability context.
 */

import { useCallback, useMemo, useState } from 'react';
import type { ReactElement, ReactNode } from 'react';
import { WindowManager, type ManagedWindow, type PanelContentRenderProps } from '../lib';
import type { SlotId } from '../lib';

import type { AppOrbState, PanelId, PanelMode } from '../types';

// ── Batch 2a migrated panels ─────────────────────────────────────────────────
import { MailPanel } from '@features/mail';
import { AgendaPanel } from '@features/agenda';
import { NotificationsPanel } from '@features/notifications';
import { TranscriptPanel } from '@features/transcript';

// ── Batch 2b migrated panels ─────────────────────────────────────────────────
import { SystemPanel } from '@features/system';
import { GitLabPanel } from '@features/gitlab';
import { NowPlayingPanel } from '@features/nowplaying';
import { LogPanel } from '@features/log';

// ── Batch 2c migrated panels ─────────────────────────────────────────────────
import { DevPanel } from '@features/dev';
import { SelfFixPanel } from '@features/selffix';

// ── Props ────────────────────────────────────────────────────────────────────

export interface HudWindowsViewProps {
    idle: boolean;
    paused?: boolean;
    orbState?: AppOrbState;
}

// ── Panel spec ───────────────────────────────────────────────────────────────

interface PanelSpec {
    id: PanelId;
    title: string;
    ix: string;
    render: (mode: PanelMode, paused: boolean, orbState: AppOrbState) => ReactNode;
}

const PANELS: ReadonlyArray<PanelSpec> = [
    {
        id: 'agenda',
        title: 'Agenda',
        ix: '▦',
        render: (mode) => <AgendaPanel mode={mode} />,
    },
    {
        id: 'mail',
        title: 'Inbox',
        ix: '✉',
        render: (mode) => <MailPanel mode={mode} />,
    },
    {
        id: 'notifications',
        title: 'Proactive',
        ix: '⚡',
        render: (mode) => <NotificationsPanel mode={mode} />,
    },
    {
        id: 'transcript',
        title: 'Transcript',
        ix: '▸',
        render: (mode, _paused, orbState) => <TranscriptPanel mode={mode} orbState={orbState} />,
    },
    {
        id: 'nowplaying',
        title: 'Now Playing',
        ix: '♫',
        render: (mode) => <NowPlayingPanel mode={mode} />,
    },
    {
        id: 'system',
        title: 'System',
        ix: '◈',
        render: (mode, paused) => <SystemPanel mode={mode} paused={paused} />,
    },
    {
        id: 'dev',
        title: 'Dev Toolkit',
        ix: '⚙',
        render: (mode) => <DevPanel mode={mode} />,
    },
    {
        id: 'selffix',
        title: 'Self-Fix',
        ix: '🔧',
        render: (mode) => <SelfFixPanel mode={mode} />,
    },
    {
        id: 'gitlab',
        title: 'GitLab',
        ix: '⬡',
        render: (mode) => <GitLabPanel mode={mode} />,
    },
    {
        id: 'log',
        title: 'Console',
        ix: '≡',
        render: (mode) => <LogPanel mode={mode} />,
    },
];

// ── Default slot assignments ─────────────────────────────────────────────────

const DEFAULT_ASSIGNMENTS: Record<string, SlotId> = {
    agenda: 'L1',
    mail: 'L2',
    notifications: 'L3',
    nowplaying: 'R1',
    system: 'R3',
    transcript: 'B1',
    dev: 'B2',
    gitlab: 'B3',
    selffix: 'B3',
    log: 'B3',
};

// ── Component ────────────────────────────────────────────────────────────────

export function HudWindowsView({
    idle,
    paused = false,
    orbState = 'idle',
}: HudWindowsViewProps): ReactElement {
    const effectivePaused = paused || idle;

    const [assignments, setAssignments] = useState<Record<string, SlotId>>(DEFAULT_ASSIGNMENTS);
    const [focusedId, setFocusedId] = useState<string | null>(null);

    const handleAssignmentsChange = useCallback((next: Record<string, SlotId>) => {
        setAssignments(next);
    }, []);

    const handleFocusChange = useCallback((id: string | null) => {
        setFocusedId(id);
    }, []);

    const managedWindows: ManagedWindow[] = useMemo(() => {
        return PANELS
            .map((spec): ManagedWindow => ({
                id: spec.id,
                title: spec.title,
                ix: spec.ix,
                itemRenderer: ({ mode }: PanelContentRenderProps) =>
                    spec.render(mode as PanelMode, effectivePaused, orbState),
            }));
    }, [effectivePaused, orbState]);

    return (
        <WindowManager
            windows={managedWindows}
            assignments={assignments}
            onAssignmentsChange={handleAssignmentsChange}
            homeAssignments={DEFAULT_ASSIGNMENTS}
            focusedId={focusedId}
            onFocusChange={handleFocusChange}
        />
    );
}

export default HudWindowsView;
