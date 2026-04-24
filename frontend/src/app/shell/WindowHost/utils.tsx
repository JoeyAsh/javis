import type { ReactNode } from 'react';
import type { PanelMode, AppOrbState } from '@common/types';
import { TranscriptPanel } from '@features/transcript';
import { SystemPanel } from '@features/system';
import { PANELS } from '../../panels';

export function renderPanel(
    id: string,
    mode: PanelMode,
    orbState: AppOrbState,
    paused: boolean,
): ReactNode {
    const spec = PANELS.find((p) => p.id === id);
    if (!spec) return null;

    if (id === 'transcript') {
        return <TranscriptPanel mode={mode} orbState={orbState} />;
    }
    if (id === 'system') {
        return <SystemPanel mode={mode} paused={paused} />;
    }
    return <spec.Component mode={mode} />;
}
