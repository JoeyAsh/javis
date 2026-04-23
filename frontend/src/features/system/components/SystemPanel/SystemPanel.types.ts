import type { PanelMode } from '@common/types';
import type { SystemMetric } from '../../types';
import type { SparkTile } from '../SystemTile';

export interface SystemPanelProps {
    metrics?: SystemMetric[];
    paused?: boolean;
    mode?: PanelMode;
}

export interface SystemCompactProps {
    tiles: SparkTile[];
}

export interface SystemExpandedProps {
    tiles: SparkTile[];
}
