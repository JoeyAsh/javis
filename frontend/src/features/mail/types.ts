/**
 * Mail feature types.
 */

export interface MailMessage {
    id: string;
    sender: string;
    subject: string;
    preview: string;
    receivedAt: string; // ISO
    isVip: boolean;
    unread: boolean;
}

/**
 * Pushed by the mail poller every `poll_interval_seconds` (default 120 s).
 * Contains the latest unread count and up to `max_unread_summary` messages.
 */
export interface MailStatePayload {
    messages: MailMessage[];
    unread_count: number;
}

/**
 * Broadcast when the backend creates a Gmail draft and is waiting for
 * verbal confirmation before sending.
 */
export interface EmailDraftPreviewPayload {
    draft_id: string;
    to: string;
    subject: string;
    body_preview: string;
    created_at: string; // ISO
}

/**
 * Broadcast after the send-confirmation flow resolves — either the email
 * was sent (`success: true`) or the draft was discarded (`success: false`).
 */
export interface EmailSendDonePayload {
    draft_id: string;
    success: boolean;
    message_id?: string;
    error?: string;
}
