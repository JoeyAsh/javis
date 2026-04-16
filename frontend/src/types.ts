export type OrbState = 'idle' | 'listening' | 'thinking' | 'speaking';

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
  | 'selffix';

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

export type WsIncoming =
  | { type: 'audio'; data: string; text: string }
  | { type: 'status'; state: OrbState }
  | { type: 'text'; text: string }
  | { type: 'system'; payload: SystemMetricsPayload };

export type WsOutgoing =
  | { type: 'transcript'; text: string; isFinal: boolean }
  | { type: 'reset' };

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
  progressMs: number;
  durationMs: number;
  playing: boolean;
  shuffle: boolean;
  repeat: 'off' | 'all' | 'one';
  device: string;
}

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
