/**
 * Types for LightsPanel — Hypermodern HUD, Sub-14.
 *
 * These are the props/data contracts for the dormant LightsPanel UI.
 * Backend wiring is tracked in issue #54 (Home Assistant integration).
 *
 * The `Zone` type models a single lighting zone (room / area). This differs
 * from the legacy `LightDevice` type in `src/types.ts` which models individual
 * bulbs. The Zone model aligns with the Home Assistant concept of a `light`
 * entity that may control multiple bulbs grouped by area.
 */

/**
 * A single lighting zone received from Home Assistant via the WS backend.
 * Backend wires this in issue #54.
 */
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

/**
 * Actions that can be dispatched for a zone.
 * Backend wires these in issue #54.
 */
export type ZoneAction =
    | { type: 'toggle' }
    | { type: 'brightness'; value: number }
    | { type: 'color'; value: string };

/**
 * Props for the dormant LightsPanel component.
 *
 * When `zones` is undefined or empty, the panel shows a placeholder.
 * When `onAction` is undefined, the panel is display-only (no interactions).
 *
 * Backend wires `zones` and `onAction` in issue #54.
 */
export interface LightsPanelProps {
    /**
     * Zones received from Home Assistant via WS backend.
     * Empty array or undefined → shows placeholder.
     * Backend wires this in #54.
     */
    zones?: Zone[];
    /**
     * Optional action dispatcher for turning zones on/off, setting brightness/color.
     * Backend wires this in #54.
     */
    onAction?: (zoneId: string, action: ZoneAction) => void;
    /**
     * PanelMode for compact/expanded switching (passed down from WindowManager via
     * the Window render function). Kept for API compatibility with other panels.
     */
    mode?: 'compact' | 'expanded';
}
