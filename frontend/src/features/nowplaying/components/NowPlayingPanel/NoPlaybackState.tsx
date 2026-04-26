import type { ReactElement } from 'react';
import styles from './NowPlayingPanel.module.css';

export function NoPlaybackState(): ReactElement {
    return (
        <div className={styles.state}>
            <span className={styles.stateLabel}>NO ACTIVE PLAYBACK</span>
        </div>
    );
}

export default NoPlaybackState;
