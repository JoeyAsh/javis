import type { ReactElement } from 'react';
import { WaveStrip } from '../WaveStrip';
import type { TrackInfoProps } from './TrackInfo.types';
import styles from './TrackInfo.module.css';

export function TrackInfo({ track }: TrackInfoProps): ReactElement {
    const hasArt = Boolean(track.albumArtUrl);

    return (
        <div className={styles.track}>
            {hasArt ? (
                <img src={track.albumArtUrl} alt={track.album} className={styles.art} />
            ) : (
                <div aria-label="Album art placeholder" className={styles.artPlaceholder}>
                    {track.monogram}
                </div>
            )}
            <div className={styles.meta}>
                <div className={styles.title}>{track.title}</div>
                <div className={styles.artist}>{track.artist}</div>
                <div className={styles.album}>{track.album}</div>
                <WaveStrip playing={track.playing} />
            </div>
        </div>
    );
}

export default TrackInfo;
