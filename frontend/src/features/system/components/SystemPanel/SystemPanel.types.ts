import type { PanelMode, SystemMetric } from '../../../../types';

export interface SystemPanelProps {
    metrics?: SystemMetric[];
    paused?: boolean;
    mode?: PanelMode;
}
