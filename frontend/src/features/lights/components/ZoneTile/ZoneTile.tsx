import type { ReactElement } from 'react';
import type { ZoneAction } from '../../types';
import type { ZoneTileProps } from './ZoneTile.types';
import styles from './ZoneTile.module.css';

export function ZoneTile({ zone, onAction }: ZoneTileProps): ReactElement {
    const handleClick = (): void => {
        onAction?.(zone.id, { type: 'toggle' } satisfies ZoneAction);
    };

    const tileClass = [styles.tile, zone.on ? styles.tileOn : ''].filter(Boolean).join(' ');
    const nameClass = [styles.name, zone.on ? styles.nameOn : ''].filter(Boolean).join(' ');
    const dotClass = [styles.dot, zone.on ? styles.dotOn : ''].filter(Boolean).join(' ');
    const barWidth = zone.on ? zone.brightness : 0;

    return (
        <div
            className={tileClass}
            onClick={handleClick}
            role="button"
            aria-label={`${zone.label}, ${zone.on ? 'on' : 'off'}`}
            aria-pressed={zone.on}
            tabIndex={0}
            onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    handleClick();
                }
            }}
            data-no-drag
        >
            <div className={styles.row1}>
                <span className={nameClass}>{zone.label}</span>
                <span className={dotClass} aria-hidden />
            </div>
            <div className={styles.bar} aria-hidden>
                <i className={styles.barFill} style={{ width: `${barWidth}%` }} />
            </div>
            <div className={styles.dim}>{zone.on ? `${zone.brightness} %` : 'AUS'}</div>
        </div>
    );
}

export default ZoneTile;
