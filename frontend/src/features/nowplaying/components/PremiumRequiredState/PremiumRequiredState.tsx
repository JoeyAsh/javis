import type { ReactElement } from 'react';
import type { PremiumRequiredStateProps } from './PremiumRequiredState.types';

const SPOTIFY_PREMIUM_URL = 'https://www.spotify.com/premium/';

export function PremiumRequiredState({ message }: PremiumRequiredStateProps): ReactElement {
    const label = message ?? 'Premium erforderlich für Wiedergabe in JARVIS';

    return (
        <div className="flex flex-col items-center gap-2 px-4 py-3 rounded border border-yellow-900/40 bg-yellow-950/20">
            <span className="font-mono text-[10px] tracking-widest text-yellow-400 uppercase text-center">
                {label}
            </span>
            <a
                href={SPOTIFY_PREMIUM_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="font-mono text-[9px] tracking-widest text-cyan-500 hover:text-cyan-300 uppercase underline underline-offset-2"
            >
                Spotify Premium aktivieren
            </a>
        </div>
    );
}

export default PremiumRequiredState;
