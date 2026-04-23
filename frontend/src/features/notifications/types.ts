/**
 * Notifications feature types.
 */

/** Server-emitted notification — shape mirrors {@link HudNotification}. */
export interface NotificationPayload {
    id: string;
    severity: 'info' | 'warning' | 'urgent';
    title: string;
    detail?: string;
    /** ISO timestamp — server sets emit time if client doesn't. */
    timestamp?: string;
}

export type NotificationSeverity = 'info' | 'warning' | 'urgent';

export interface HudNotification {
    id: string;
    severity: NotificationSeverity;
    title: string;
    detail: string;
    timestamp: string; // ISO
}
