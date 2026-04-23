/**
 * LogView — log stream + turn timeline panel content.
 * Thin wrapper around legacy LogPanel during Phase 3 migration.
 * TODO: Rewrite internals to use lib primitives.
 */
export { LogPanel as LogView, LogPanel as default } from '../components/panels/Log/LogPanel';
export type { LogPanelProps as LogViewProps } from '../components/panels/Log/LogPanel';

