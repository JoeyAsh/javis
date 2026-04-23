import type { PanelMode } from '@common/types';
import type { LogLinePayload } from '../../types';

export interface LogPanelProps {
    mode: PanelMode;
}

export interface StreamViewProps {
    lines: ReadonlyArray<LogLinePayload>;
    onClear: () => void;
}
