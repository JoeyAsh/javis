import type { Zone, ZoneAction } from '../../types';

export interface LightsPanelProps {
    /**
     * Zones received from Home Assistant via WS backend.
     * Empty array or undefined → shows placeholder.
     * Backend wires this in #54.
     */
    zones?: Zone[];
    /**
     * Optional action dispatcher. Backend wires this in #54.
     */
    onAction?: (zoneId: string, action: ZoneAction) => void;
    /**
     * PanelMode for compact/expanded switching.
     */
    mode?: 'compact' | 'expanded';
}
