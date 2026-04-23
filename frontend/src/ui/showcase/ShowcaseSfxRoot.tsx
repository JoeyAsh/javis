/**
 * ShowcaseSfxRoot — mounts the Web Audio engine for the standalone Showcase
 * app and exposes mute controls to descendants via ShowcaseSfxContext.
 *
 * Hardcoded params:
 *   orbState='idle'   → state machine stays quiet; only ambient runs after boot
 *   connected=true    → suppresses disconnect/offline SFX
 *   heartbeatEnabled=false → no heartbeat loop in Showcase
 */

import { createContext, useContext, type ReactElement, type ReactNode } from 'react';
import { useAudioEngine, SfxProvider } from '@core/audio';

/* ---- Mute context ---- */

interface ShowcaseSfxContextValue {
    isMuted: boolean;
    toggleMute: () => void;
}

const ShowcaseSfxContext = createContext<ShowcaseSfxContextValue>({
    isMuted: false,
    toggleMute: () => undefined,
});

export function useShowcaseSfx(): ShowcaseSfxContextValue {
    return useContext(ShowcaseSfxContext);
}

/* ---- Provider ---- */

interface ShowcaseSfxRootProps {
    children: ReactNode;
}

export function ShowcaseSfxRoot({ children }: ShowcaseSfxRootProps): ReactElement {
    const { isMuted, toggleMute, playOneShot, play, stop } = useAudioEngine(
        'idle',
        true,
        false,
    );

    return (
        <ShowcaseSfxContext.Provider value={{ isMuted, toggleMute }}>
            <SfxProvider playOneShot={playOneShot} play={play} stop={stop}>
                {children}
            </SfxProvider>
        </ShowcaseSfxContext.Provider>
    );
}

export default ShowcaseSfxRoot;
