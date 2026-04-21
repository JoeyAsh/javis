/**
 * SystemTile — single metric tile (label + value + sparkline).
 * Matches prototype `.tile` pattern exactly.
 */
import type { ReactElement } from 'react';
import type { SystemMetric } from '../../../types';
import { Sparkline } from './Sparkline';
import './SystemPanel.css';

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

function isWarn(tile: SparkTile): boolean {
    if (tile.current === null) return false;
    return (
        (tile.id === 'cpu' && tile.current > 85) ||
        (tile.id === 'cpuTemp' && tile.current > 80) ||
        (tile.id === 'ram' && tile.current > 90)
    );
}

export function SystemTile({ tile }: SystemTileProps): ReactElement {
    const warn = isWarn(tile);

    if (tile.current === null) {
        return (
            <div className="system-tile">
                <div className="system-tile__header">
                    <span className="system-tile__label">{tile.label}</span>
                    <span className="system-tile__na">n/a</span>
                </div>
                <div className="system-tile__na-line" />
            </div>
        );
    }

    const precision = tile.id === 'net' ? 1 : 0;

    return (
        <div className={`system-tile${warn ? ' system-tile--warn' : ''}`}>
            <div className="system-tile__header">
                <span className="system-tile__label">{tile.label}</span>
                <span className="system-tile__value">
                    {tile.current.toFixed(precision)}
                    <span className="system-tile__unit">{tile.unit}</span>
                </span>
            </div>
            <Sparkline values={tile.history} color="var(--accent-bright)" warn={warn} />
            {tile.secondary !== undefined && (
                <div className="system-tile__sub">
                    {tile.secondaryLabel} {tile.secondary.toFixed(1)}
                </div>
            )}
        </div>
    );
}

export default SystemTile;
