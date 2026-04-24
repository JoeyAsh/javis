import type { SparkTile } from './SystemTile.types';

export function isWarn(tile: SparkTile): boolean {
    if (tile.current === null) return false;
    return (
        (tile.id === 'cpu' && tile.current > 85) ||
        (tile.id === 'cpuTemp' && tile.current > 80) ||
        (tile.id === 'ram' && tile.current > 90)
    );
}
