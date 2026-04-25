import type { SystemMetric } from '../../types';

export interface SparkTile {
    id: SystemMetric['id'];
    label: string;
    unit: string;
    current: number | null;
    history: number[];
    secondary?: number;
    secondaryLabel?: string;
}

export interface SystemTileProps {
    tile: SparkTile;
}
