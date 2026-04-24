import type { PanelMode } from '@common/types';
import type { LogLinePayload } from '../../types';

export type TabId = 'stream' | 'timeline';

export interface LogPanelProps {
    mode: PanelMode;
}

export interface StreamViewProps {
    lines: ReadonlyArray<LogLinePayload>;
    onClear: () => void;
}
