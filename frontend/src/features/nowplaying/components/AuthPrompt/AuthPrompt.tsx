import { useCallback } from 'react';
import type { ReactElement } from 'react';
import { SPOTIFY_AUTH_URL } from '../../constants';
import styles from './AuthPrompt.module.css';

export function AuthPrompt(): ReactElement {
    const handleConnect = useCallback(() => {
        window.open(SPOTIFY_AUTH_URL, '_blank', 'noopener,noreferrer');
    }, []);

    return (
        <div className={styles.state}>
            <span className={styles.label}>SPOTIFY — NICHT VERBUNDEN</span>
            <button
                type="button"
                aria-label="Log in to Spotify"
                className={styles.btn}
                onClick={handleConnect}
            >
                VERBINDEN
            </button>
        </div>
    );
}

export default AuthPrompt;
