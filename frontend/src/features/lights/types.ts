/**
 * Lights feature types.
 * Zone model aligns with the Home Assistant concept of a light entity.
 * Backend wiring tracked in issue #54.
 */

/** A single lighting zone received from Home Assistant via the WS backend. */
export interface Zone {
    /** Unique entity ID — e.g. "light.living_room", "lr", "kt" */
    id: string;
    /** Human-readable display label — e.g. "Living Room", "Kitchen" */
    label: string;
    /** Whether the zone is currently on */
    on: boolean;
    /** Brightness percentage 0–100 */
    brightness: number;
    /** Optional color — hex or CSS named color */
    color?: string;
    /** Whether the zone has an active scene applied */
    active?: boolean;
}

/** Actions that can be dispatched for a zone. */
export type ZoneAction =
    | { type: 'toggle' }
    | { type: 'brightness'; value: number }
    | { type: 'color'; value: string };

export interface LightsState {
    zones: Zone[];
}
