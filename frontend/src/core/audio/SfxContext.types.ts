import type { ReactNode } from 'react';
import type { SfxEvent } from './config';

export interface SfxContextValue {
    playOneShot: (event: SfxEvent) => void;
    play: (event: SfxEvent) => void;
    stop: (event: SfxEvent) => void;
}

export interface SfxProviderProps {
    playOneShot: (event: SfxEvent) => void;
    play: (event: SfxEvent) => void;
    stop: (event: SfxEvent) => void;
    children: ReactNode;
}
