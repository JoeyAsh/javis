// Modular panel folders — Batch 2a+2b migrated panels are now in features/
// MailPanel, AgendaPanel, NotificationsPanel, TranscriptPanel → @features/*/
// GitLabPanel, NowPlayingPanel, SystemPanel, LogPanel → @features/*/
export { GitLabPanel } from '@features/gitlab';
export { NowPlayingPanel } from '@features/nowplaying';
export { SystemPanel } from '@features/system';
export { DevPanel } from './Dev';
export { LogPanel } from '@features/log';

/* LightsPanel registered but NOT mounted by default — awaiting backend follow-up #54 */
export { LightsPanel } from './Lights';

// Untouched panel (epic #40 out-of-scope)
export { SelfFixPanel } from './SelfFixPanel';
