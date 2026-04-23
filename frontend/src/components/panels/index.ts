// Modular panel folders — Batch 2a migrated panels are now in features/
// MailPanel, AgendaPanel, NotificationsPanel, TranscriptPanel → @features/*/
export { GitLabPanel } from './GitLab';
export { NowPlayingPanel } from './NowPlaying';
export { SystemPanel } from './System';
export { DevPanel } from './Dev';
export { LogPanel } from './Log';

/* LightsPanel registered but NOT mounted by default — awaiting backend follow-up #54 */
export { LightsPanel } from './Lights';

// Untouched panel (epic #40 out-of-scope)
export { SelfFixPanel } from './SelfFixPanel';
