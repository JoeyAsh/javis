export type PanelId =
    | 'agenda'
    | 'mail'
    | 'nowplaying'
    | 'lights'
    | 'system'
    | 'dev'
    | 'notifications'
    | 'transcript'
    | 'selffix'
    | 'gitlab'
    | 'log';

export type PanelMode = 'compact' | 'expanded';

// Re-export SlotId from lib/layout until Sub-Call 2 moves it to @ui.
export type { SlotId } from '../../lib/layout/SlotGrid';
