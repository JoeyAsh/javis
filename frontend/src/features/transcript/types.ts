/**
 * Transcript feature types.
 */

export interface TranscriptPayload {
    role: 'user' | 'jarvis';
    text: string;
}

export type TranscriptRole = 'user' | 'jarvis';

export interface TranscriptTurn {
    id: string;
    role: TranscriptRole;
    text: string;
    at: string; // ISO
    salutation?: 'Sir' | 'Johannes';
}
