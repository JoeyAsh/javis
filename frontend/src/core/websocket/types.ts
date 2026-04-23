/**
 * WebSocket message types for the JARVIS backend.
 * Copied from src/types.ts — originals remain untouched.
 * Payload interfaces are re-exported from src/types.ts for now;
 * they will be distributed to features in later batches.
 */

export type {
    SystemMetricsPayload,
    TranscriptPayload,
    NotificationPayload,
    ConversationModePayload,
    ToolCallPayload,
    MailStatePayload,
    EmailDraftPreviewPayload,
    EmailSendDonePayload,
    SpotifyStatePayload,
    SpotifyCmdAction,
    GitHubStatePayload,
    CalendarStatePayload,
    CalendarOpPreviewPayload,
    CalendarOpDonePayload,
    GitLabStatePayload,
    LogLinePayload,
    TurnTimingPayload,
    OrbState,
} from '../../types';

export type { WsIncoming, WsOutgoing } from '../../types';
