/**
 * Agenda feature types.
 */

export interface AgendaEvent {
    id: string;
    title: string;
    start: string; // ISO
    end: string; // ISO
    location?: string;
    calendar: string;
    minutesToNext?: number;
}

/**
 * Pushed by the calendar poller every `poll_interval_seconds` (default 60 s).
 * Contains the upcoming events for the next 48 hours.
 */
export interface CalendarStatePayload {
    events: AgendaEvent[];
    dateLabel: string;
}

/**
 * Broadcast before the backend waits for voice confirmation on a
 * calendar create/update/delete operation.
 */
export interface CalendarOpPreviewPayload {
    op: 'create' | 'update' | 'delete';
    title: string;
    start: string; // ISO
    end: string; // ISO
    confirm_prompt: string;
}

/**
 * Broadcast after the calendar operation confirmation resolves — either
 * the event was modified (`success: true`) or the op was discarded.
 */
export interface CalendarOpDonePayload {
    op: 'create' | 'update' | 'delete';
    success: boolean;
    event_id?: string;
    error?: string;
}
