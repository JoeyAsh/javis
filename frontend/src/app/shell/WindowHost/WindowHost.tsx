/**
 * WindowHost — renders all JARVIS panels inside the lib WindowManager.
 *
 * Consumes the canonical PANELS registry from app/panels.ts.
 * TranscriptPanel receives orbState as an extra prop for its thinking indicator.
 * SystemPanel receives paused so it can pause expensive polling when idle.
 */

import { useCallback, useMemo, useState } from 'react';
import type { ReactElement, ReactNode } from 'react';
import { WindowManager } from '@ui';
import type { ManagedWindow, PanelContentRenderProps } from '@ui';
import type { SlotId } from '@common/types';
import type { PanelMode } from '@common/types';
import { PANELS, DEFAULT_ASSIGNMENTS } from '../../panels';
import type { WindowHostProps } from './WindowHost.types';
import { renderPanel } from './utils';

export function WindowHost({ idle, orbState = 'idle' }: WindowHostProps): ReactElement {
    const effectivePaused = idle;

    const [assignments, setAssignments] = useState<Record<string, SlotId>>(DEFAULT_ASSIGNMENTS);
    const [focusedId, setFocusedId] = useState<string | null>(null);

    const handleAssignmentsChange = useCallback((next: Record<string, SlotId>) => {
        setAssignments(next);
    }, []);

    const handleFocusChange = useCallback((id: string | null) => {
        setFocusedId(id);
    }, []);

    const managedWindows: ManagedWindow[] = useMemo(() => {
        return PANELS.map((spec): ManagedWindow => ({
            id: spec.id,
            title: spec.title,
            ix: spec.icon,
            itemRenderer: ({ mode }: PanelContentRenderProps): ReactNode =>
                renderPanel(spec.id, mode as PanelMode, orbState, effectivePaused),
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

export default WindowHost;
