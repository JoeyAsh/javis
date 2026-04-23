/**
 * SelfFixView — self-fix entries panel content.
 * Thin wrapper around legacy SelfFixPanel during Phase 3 migration.
 * TODO: Rewrite internals to use lib primitives.
 */
export {
    SelfFixPanel as SelfFixView,
    SelfFixPanel as default,
} from '../components/panels/SelfFixPanel';
export type { SelfFixPanelProps as SelfFixViewProps } from '../components/panels/SelfFixPanel';

