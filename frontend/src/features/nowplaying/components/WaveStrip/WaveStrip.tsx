import type { ReactElement } from 'react';
import { WAVE_BARS } from '../../constants';
import type { WaveStripProps } from './WaveStrip.types';
import styles from './WaveStrip.module.css';

export function WaveStrip({ playing }: WaveStripProps): ReactElement {
    return (
        <div
            className={`${styles.wave}${playing ? '' : ` ${styles.paused}`}`}
            aria-hidden
        >
            {Array.from({ length: WAVE_BARS }, (_, i) => (
                <div
                    key={i}
                    className={styles.bar}
                    style={{
                        height: `${30 + ((i * 17) % 70)}%`,
                        animationDelay: `${(i * 0.12).toFixed(2)}s`,
                    }}
                />
            ))}
        </div>
    );
}

export default WaveStrip;
