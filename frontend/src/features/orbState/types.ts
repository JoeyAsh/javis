/**
 * orbState feature types.
 * OrbState and AppOrbState are the single source of truth from @common/types.
 */
export type { OrbState, AppOrbState } from '@common/types';

/** Payload for an OpenClaw tool-call lifecycle event. */
export interface ToolCallPayload {
    state: 'started' | 'finished';
    tool_name: string;
    /** Human-readable description of what the tool is doing. */
    summary: string;
}
