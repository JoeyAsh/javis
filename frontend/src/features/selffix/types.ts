/**
 * SelfFix feature types.
 * Moved from src/types.ts.
 */

export type SelfFixStatus = 'in_progress' | 'completed' | 'failed';

export interface SelfFixEntry {
    id: string;
    status: SelfFixStatus;
    summary: string;
    detail: string;
    commitSha?: string;
    added?: number;
    removed?: number;
    startedAt: string; // ISO
}
