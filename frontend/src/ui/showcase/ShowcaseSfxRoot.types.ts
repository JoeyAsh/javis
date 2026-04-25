import type { ReactNode } from 'react';

export interface ShowcaseSfxContextValue {
    isMuted: boolean;
    toggleMute: () => void;
}

export interface ShowcaseSfxRootProps {
    children: ReactNode;
}
