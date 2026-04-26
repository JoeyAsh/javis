/**
 * WebSocket message types for the JARVIS backend.
 * All payload types are imported from their canonical feature modules.
 */

export type { OrbState } from '@common/types';
export type { SystemMetricsPayload } from '@features/system/types';
export type { TranscriptPayload } from '@features/transcript/types';
export type {
    NotificationPayload,
    HudNotification,
    NotificationSeverity,
} from '@features/notifications/types';
export type { ConversationModePayload } from '@features/conversation/types';
export type { ToolCallPayload } from '@features/orbState/types';
export type {
    MailStatePayload,
    MailMessage,
    EmailDraftPreviewPayload,
    EmailSendDonePayload,
} from '@features/mail/types';
export type {
    SpotifyStatePayload,
    SpotifyCmdAction,
    NowPlayingTrack,
} from '@features/nowplaying/types';
export type { GitHubStatePayload } from '@features/dev/types';
export type {
    CalendarStatePayload,
    CalendarOpPreviewPayload,
    CalendarOpDonePayload,
    AgendaEvent,
} from '@features/agenda/types';
export type { GitLabStatePayload } from '@features/gitlab/types';
export type { LogLinePayload, TurnTimingPayload } from '@features/log/types';

import type { OrbState } from '@common/types';
import type { SystemMetricsPayload } from '@features/system/types';
import type { TranscriptPayload } from '@features/transcript/types';
import type { NotificationPayload } from '@features/notifications/types';
import type { ConversationModePayload } from '@features/conversation/types';
import type { ToolCallPayload } from '@features/orbState/types';
import type { MailStatePayload, EmailDraftPreviewPayload, EmailSendDonePayload } from '@features/mail/types';
import type { SpotifyStatePayload, SpotifyCmdAction } from '@features/nowplaying/types';
import type { GitHubStatePayload } from '@features/dev/types';
import type { CalendarStatePayload, CalendarOpPreviewPayload, CalendarOpDonePayload } from '@features/agenda/types';
import type { GitLabStatePayload } from '@features/gitlab/types';
import type { LogLinePayload, TurnTimingPayload } from '@features/log/types';

export type WsIncoming =
    | {
          type: 'audio';
          data: string;
          text: string;
          /** Optional channel tag — ``"backchannel"`` means lower volume (0.3); ``"notification"`` defers behind speech. */
          channel?: 'backchannel' | 'notification';
      }
    | { type: 'status'; state: OrbState }
    | { type: 'text'; text: string }
    | { type: 'system'; payload: SystemMetricsPayload }
    | { type: 'transcript'; payload: TranscriptPayload }
    | { type: 'notification'; payload: NotificationPayload }
    | { type: 'conversation_mode'; payload: ConversationModePayload }
    /** Backend detected user speech during TTS playback. Frontend must clear
     *  the audio queue and stop any currently playing clip. */
    | { type: 'barge_in' }
    /** OpenClaw tool-call lifecycle event. Used to drive the `working` orb state. */
    | { type: 'tool_call'; payload: ToolCallPayload }
    /** Live mail state pushed by the backend polling coroutine. */
    | { type: 'mail_state'; payload: MailStatePayload }
    /**
     * Backend has composed a draft and is waiting for verbal confirmation.
     * The HUD should show the draft preview until `email_send_done` arrives.
     */
    | { type: 'email_draft_preview'; payload: EmailDraftPreviewPayload }
    /** The send-confirmation flow completed (either sent or aborted). */
    | { type: 'email_send_done'; payload: EmailSendDonePayload }
    /** Live Spotify playback state broadcast by the backend polling loop. */
    | { type: 'spotify_state'; payload: SpotifyStatePayload }
    /** Live GitHub state broadcast by the backend polling loop. */
    | { type: 'github_state'; payload: GitHubStatePayload }
    /** Live Google Calendar state pushed by the backend polling coroutine. */
    | { type: 'calendar_state'; payload: CalendarStatePayload }
    /** Backend proposes a calendar op and waits for voice confirmation. */
    | { type: 'calendar_op_preview'; payload: CalendarOpPreviewPayload }
    /** The calendar op confirmation flow resolved. */
    | { type: 'calendar_op_done'; payload: CalendarOpDonePayload }
    /** Live GitLab state broadcast by the backend polling loop. */
    | { type: 'gitlab_state'; payload: GitLabStatePayload }
    /** Backend log line from the loguru WS sink. */
    | { type: 'log_line'; payload: LogLinePayload }
    /** Per-voice-turn latency waterfall emitted at end of each turn. */
    | { type: 'turn_timing'; payload: TurnTimingPayload };

export type WsOutgoing =
    | { type: 'transcript'; text: string; isFinal: boolean }
    | { type: 'reset' }
    /**
     * STOP button — request the backend to abort any in-flight voice turn.
     */
    | { type: 'cancel_turn' }
    /**
     * Panel transport / volume command sent to the backend.
     */
    | { type: 'spotify_cmd'; payload: { action: SpotifyCmdAction; value?: number } };
