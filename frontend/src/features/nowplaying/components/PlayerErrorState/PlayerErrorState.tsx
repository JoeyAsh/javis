import type { ReactElement } from 'react';
import type { PlayerErrorStateProps } from './PlayerErrorState.types';

const ERROR_TITLES: Record<string, string> = {
    authentication_error: 'Authentifizierung abgelaufen, bitte neu anmelden',
    account_error: 'Premium-Konto für Wiedergabe erforderlich',
    initialization_error: 'SDK konnte nicht initialisiert werden',
    playback_error: 'Wiedergabefehler',
};

export function PlayerErrorState({ error }: PlayerErrorStateProps): ReactElement {
    const title = ERROR_TITLES[error.kind] ?? 'Unbekannter Fehler';

    return (
        <div className="flex flex-col gap-1 px-3 py-2 rounded border border-red-900/40 bg-red-950/20">
            <span className="font-mono text-[10px] tracking-widest text-red-400 uppercase">
                {title}
            </span>
            <span className="font-mono text-[9px] text-red-600/70 break-all">
                {error.message}
            </span>
        </div>
    );
}

export default PlayerErrorState;
