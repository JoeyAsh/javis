/**
 * MailView — mail panel content.
 * Thin wrapper around legacy MailPanel during Phase 3 migration.
 * TODO: Rewrite internals to use lib primitives.
 */
export { MailPanel as MailView, MailPanel as default } from '../components/panels/Mail/MailPanel';
export type { MailPanelProps as MailViewProps } from '../components/panels/Mail/MailPanel';

