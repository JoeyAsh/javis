/**
 * States that drive the JARVIS orb visual and audio state machine.
 * Single source of truth — copied from src/types.ts.
 */
export type OrbState =
    | 'idle'
    | 'listening'
    | 'thinking'
    | 'speaking'
    /**
     * Follow-up window after a successful voice turn. The mic stays open
     * for the configured window (default 18 s) so the user can keep
     * talking without repeating the wake word. Visually a subtler pulse
     * than full `listening`.
     */
    | 'follow_up';

/**
 * Full app-layer orb state — a superset of {@link OrbState} that includes
 * states handled above the base state machine.
 *
 * Components and hooks should use `AppOrbState` for their props / return values.
 */
export type AppOrbState =
    | OrbState
    /**
     * JARVIS is executing a tool call (file read, shell, edit, etc.) in the
     * background. The amber CSS overlay provides the visual distinction.
     * Orb stays `working` while any tool call is in-flight.
     */
    | 'working';
