/**
 * Conversation feature types.
 */

/**
 * Server-emitted conversation-mode update — sent when the follow-up
 * window is armed (after a successful turn) and again when it expires
 * or is closed by a sleep phrase.
 */
export interface ConversationModePayload {
    active: boolean;
    seconds_remaining: number;
}
