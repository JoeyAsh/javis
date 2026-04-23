import type { ReactElement } from 'react';
import { Sparkline } from '../Sparkline';
import type { SystemTileProps, SparkTile } from './SystemTile.types';
import styles from './SystemTile.module.css';

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
            <div className={styles.tile}>
                <div className={styles.header}>
                    <span className={styles.label}>{tile.label}</span>
                    <span className={styles.na}>n/a</span>
                </div>
                <div className={styles.naLine} />
            </div>
        );
    }

    const precision = tile.id === 'net' ? 1 : 0;

    return (
        <div className={`${styles.tile}${warn ? ` ${styles.warn}` : ''}`}>
            <div className={styles.header}>
                <span className={styles.label}>{tile.label}</span>
                <span className={styles.value}>
                    {tile.current.toFixed(precision)}
                    <span className={styles.unit}>{tile.unit}</span>
                </span>
            </div>
            <Sparkline values={tile.history} color="var(--accent-bright)" warn={warn} />
            {tile.secondary !== undefined && (
                <div className={styles.sub}>
                    {tile.secondaryLabel} {tile.secondary.toFixed(1)}
                </div>
            )}
        </div>
    );
}

export default SystemTile;
