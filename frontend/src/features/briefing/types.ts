/**
 * Briefing feature types — WS payload + slice state.
 */

export interface BriefingMail {
    sender: string;
    subject: string;
    receivedAt: string; // ISO
}

export interface BriefingHeadline {
    title: string;
    url: string | null;
    publishedAt: string | null;
}

export interface BriefingEvent {
    start: string; // ISO
    title: string;
}

export interface BriefingWeather {
    location: string;
    condition: string;
    currentTemp: number;
    high: number;
    low: number;
}

export type BriefingCommute = {
    summary?: string;
    durationMinutes?: number;
} | null;

export interface BriefingPayload {
    weather: BriefingWeather | null;
    events: BriefingEvent[];
    commute: BriefingCommute;
    mails: BriefingMail[];
    headlines: BriefingHeadline[];
    generatedAt: string; // ISO
    language: 'de' | 'en';
}

/** Alias used by briefingApi for the WS-level payload envelope. */
export type BriefingStatePayload = BriefingPayload;

export interface BriefingState {
    payload: BriefingPayload | null;
    /** Local ISO timestamp of when we received the message — used for 4 h auto-clear. */
    receivedAt: string | null;
}
