import type { Zone, ZoneAction } from '../../types';

export interface ZoneTileProps {
    zone: Zone;
    /** Called when the user interacts with the tile. Undefined → tile is display-only. */
    onAction?: (zoneId: string, action: ZoneAction) => void;
}
