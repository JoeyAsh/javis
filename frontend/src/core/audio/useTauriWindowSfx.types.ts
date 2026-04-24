import type { SfxEvent } from './config';

export interface TauriWindowSfxProps {
    playOneShot: (event: SfxEvent) => void;
}
