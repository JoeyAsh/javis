/**
 * States that the Three.js orb engine (`lib/orb.ts`) natively understands.
 * This type is kept in sync with the engine's switch statement — do NOT add
 * states here unless you also add a corresponding case in `orb.ts`.
 */
export type OrbState =
  | 'idle'
  | 'listening'
  | 'thinking'
  | 'speaking'
  /**
   * Follow-up window after a successful voice turn. The mic stays open
   * for the configured window (default 18 s) so the user can keep
   * talking without repeating the wake word. Visually a subtler pulse
   * than full `listening` — see `setFollowUp` in ``lib/orb.ts``.
   */
  | 'follow_up';

/**
 * Full app-layer orb state — a superset of {@link OrbState} that includes
 * states which are handled above the engine layer (e.g. via CSS overlays or
 * by remapping to a base engine state before calling `orb.setState`).
 *
 * Components and hooks should use `AppOrbState` for their props / return
 * values; only the `OrbCanvas` → engine boundary uses `OrbState`.
 */
export type AppOrbState =
  | OrbState
  /**
   * JARVIS is executing a tool call (file read, shell, edit, etc.) in the
   * background. Mapped to `thinking` when passed to the orb engine; the
   * amber CSS mix-blend overlay on `OrbCanvas` provides the visual
   * distinction. Orb stays `working` while any tool call is in-flight.
   */
  | 'working';

// ============ HUD window system ============

export type PanelId =
  | 'agenda'
  | 'mail'
  | 'nowplaying'
  | 'lights'
  | 'system'
  | 'dev'
  | 'notifications'
  | 'transcript'
  | 'selffix'
  | 'gitlab'
  | 'log';

export type PanelMode = 'compact' | 'expanded';

// ============ Existing WS ============

/**
 * Live system metrics payload from the backend.
 *
 * `cpu`, `mem`, `uptime` are required (legacy-compatible). The remaining
 * fields are surfaced by the new {@link SystemMetricsCollector} and may
 * be `null` if the host doesn't expose that sensor (e.g. `gpu` on an
 * AMD-only box, or `cpu_temp` in a container without /sys access).
 */
export interface SystemMetricsPayload {
  cpu: number;
  mem: number;
  uptime: string;
  gpu?: number | null;
  cpu_temp?: number | null;
  net_up?: number;
  net_down?: number;
  disk?: number;
}

export interface TranscriptPayload {
  role: 'user' | 'jarvis';
  text: string;
}

/** Server-emitted notification — shape mirrors {@link HudNotification}. */
export interface NotificationPayload {
  id: string;
  severity: 'info' | 'warning' | 'urgent';
  title: string;
  detail?: string;
  /** ISO timestamp — server sets emit time if client doesn't. */
  timestamp?: string;
}

/**
 * Server-emitted conversation-mode update — sent when the follow-up
 * window is armed (after a successful turn) and again when it expires
 * or is closed by a sleep phrase. Used by the HUD to drive the orb's
 * muted pulse + last-5 s countdown ring.
 */
export interface ConversationModePayload {
  active: boolean;
  seconds_remaining: number;
}

/** Payload for an OpenClaw tool-call lifecycle event. */
export interface ToolCallPayload {
  state: 'started' | 'finished';
  tool_name: string;
  /** Human-readable description of what the tool is doing, e.g. "Lese config/config.yaml". */
  summary: string;
}

// ============ Gmail / Mail WS payloads ============

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

// ============ Google Calendar WS payloads ============

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
   * STOP button — request the backend to abort any in-flight voice turn
   * (STT / LLM / TTS) for this connection. Idempotent; safe to send when
   * nothing is running. The backend replies with a ``status=idle`` frame
   * and an info notification titled "Konversation gestoppt".
   */
  | { type: 'cancel_turn' }
  /**
   * Panel transport / volume command sent to the backend.
   * Phase 1: backend logs receipt only; actual control flows via voice → OpenClaw.
   */
  | { type: 'spotify_cmd'; payload: { action: SpotifyCmdAction; value?: number } };

// ============ HUD mock types ============

export interface AgendaEvent {
  id: string;
  title: string;
  start: string; // ISO
  end: string; // ISO
  location?: string;
  calendar: string;
  minutesToNext?: number;
}

export interface MailMessage {
  id: string;
  sender: string;
  subject: string;
  preview: string;
  receivedAt: string; // ISO
  isVip: boolean;
  unread: boolean;
}

export interface NowPlayingTrack {
  title: string;
  artist: string;
  album: string;
  monogram: string;
  albumArtUrl?: string;
  progressMs: number;
  durationMs: number;
  playing: boolean;
  shuffle: boolean;
  repeat: 'off' | 'all' | 'one';
  device: string;
}

// ============ Spotify WS payloads ============

export interface SpotifyTrackPayload {
  name: string;
  artist: string;
  album: string;
  albumArtUrl?: string;
  durationMs: number;
  progressMs: number;
  isPlaying: boolean;
}

export interface SpotifyDevicePayload {
  name: string;
  type: string;
  volumePercent: number;
}

/**
 * Broadcast every `poll_interval_seconds` from the backend Spotify loop.
 * When `authenticated` is false, track and device are absent.
 */
export interface SpotifyStatePayload {
  authenticated: boolean;
  track?: SpotifyTrackPayload;
  device?: SpotifyDevicePayload;
  error?: string;
}

export type SpotifyCmdAction = 'play' | 'pause' | 'next' | 'prev' | 'volume';

export interface LightDevice {
  id: string;
  name: string;
  on: boolean;
  brightness: number; // 0-100
  color: string; // hex
}

export type LightScene = 'Cozy' | 'Focus' | 'Movie' | 'Alert';

export interface LightsState {
  devices: LightDevice[];
  activeScene: LightScene | null;
}

export interface SystemMetric {
  id: 'cpu' | 'ram' | 'gpu' | 'cpuTemp' | 'net' | 'disk';
  label: string;
  unit: string;
  current: number;
  history: number[];
  secondary?: number; // e.g. net down vs up
  secondaryLabel?: string;
}

export interface GithubPR {
  id: string;
  repo: string;
  title: string;
  author: string;
  age: string;
}

export interface GithubNotification {
  id: string;
  repo: string;
  reason: string;
  title: string;
  age: string;
}

// ============ GitHub live WS payloads ============

export interface GithubPRLive {
  id: string;
  repo: string;
  title: string;
  author: string;
  html_url: string;
  updated_at: string; // ISO
}

export interface GithubIssueLive {
  id: string;
  repo: string;
  title: string;
  html_url: string;
  updated_at: string; // ISO
}

export interface GithubCIRunLive {
  repo: string;
  status: 'success' | 'failure' | 'running' | 'pending';
  ran_at: string; // ISO
  html_url: string;
}

/**
 * Broadcast every `poll_interval_seconds` from the backend GitHub poller.
 * `stale: true` means the last poll failed and this is cached data.
 */
export interface GitHubStatePayload {
  prs: GithubPRLive[];
  issues: GithubIssueLive[];
  ci: GithubCIRunLive[];
  fetched_at: string; // ISO
  stale: boolean;
}

export type RepoSyncStatus = 'clean' | 'dirty' | 'ahead' | 'behind';

export interface LocalRepo {
  id: string;
  name: string;
  branch: string;
  status: RepoSyncStatus;
  ahead: number;
  behind: number;
  uncommitted: number;
}

export interface DockerContainer {
  id: string;
  name: string;
  image: string;
  status: 'running' | 'exited' | 'restarting';
  cpu: number; // 0-100
  mem: number; // 0-100
}

export type CIStatus = 'success' | 'failure' | 'running' | 'pending';

export interface CIRun {
  id: string;
  repo: string;
  status: CIStatus;
  ranAt: string; // ISO
  duration: string;
}

export interface DevToolkitMock {
  prs: GithubPR[];
  notifications: GithubNotification[];
  repos: LocalRepo[];
  docker: DockerContainer[];
  ci: CIRun[];
}

export type NotificationSeverity = 'info' | 'warning' | 'urgent';

export interface HudNotification {
  id: string;
  severity: NotificationSeverity;
  title: string;
  detail: string;
  timestamp: string; // ISO
}

export type TranscriptRole = 'user' | 'jarvis';

export interface TranscriptTurn {
  id: string;
  role: TranscriptRole;
  text: string;
  at: string; // ISO
  salutation?: 'Sir' | 'Johannes';
}

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

// ============ Log panel WS payloads ============

/** Log severity levels emitted by the backend loguru sink. */
export type LogLevel = 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';

/**
 * A single backend log line broadcast via the ``log_line`` WS message type.
 * All timestamps are Unix epoch milliseconds.
 */
export interface LogLinePayload {
  timestamp: number;
  level: LogLevel;
  module: string;
  message: string;
}

/**
 * Per-voice-turn latency breakdown broadcast via the ``turn_timing`` WS message.
 * All ``*_ts`` fields are Unix epoch milliseconds. Fields may be ``null`` when
 * a phase was skipped (e.g. no TTS audio produced for a sleep-phrase turn).
 */
export interface TurnTimingPayload {
  turn_id: string;
  /** Epoch ms when the audio buffer was handed off to STT. */
  audio_end_ts: number;
  /** Epoch ms when STT returned a transcript. */
  stt_done_ts: number;
  /** Epoch ms when the first LLM text token arrived (TTFT). Null if cancelled. */
  llm_first_token_ts: number | null;
  /** Epoch ms when the full LLM response stream completed. */
  llm_done_ts: number;
  /** Epoch ms when the first TTS audio chunk was broadcast. Null if no audio. */
  tts_first_audio_ts: number | null;
  /** Epoch ms when TTS stream ended (last chunk broadcast). */
  tts_done_ts: number;
}

// ============ GitLab WS payloads ============

/** A single open GitLab merge request assigned to the authenticated user. */
export interface GitLabMRPayload {
  id: number;
  iid: number;
  title: string;
  source_branch: string;
  web_url: string;
  author: string;
  created_at: string; // ISO 8601
  draft: boolean;
}

/** A single open GitLab issue assigned to the authenticated user. */
export interface GitLabIssuePayload {
  id: number;
  iid: number;
  title: string;
  labels: string[];
  web_url: string;
  author: string;
  created_at: string; // ISO 8601
}

/** The most recent pipeline for a configured project. */
export interface GitLabPipelinePayload {
  project: string;
  status: 'success' | 'failed' | 'running' | 'pending' | 'canceled' | 'skipped';
  web_url: string;
  created_at: string; // ISO 8601
}

/**
 * Broadcast every `poll_interval_seconds` from the backend GitLab poller.
 * `error` is non-null when the last fetch failed (partially or completely).
 */
export interface GitLabStatePayload {
  mrs: GitLabMRPayload[];
  issues: GitLabIssuePayload[];
  pipelines: GitLabPipelinePayload[];
  error: string | null;
}
