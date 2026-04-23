/**
 * GitLabView — GitLab work-items panel content.
 * Thin wrapper around legacy GitLabPanel during Phase 3 migration.
 * TODO: Rewrite internals to use lib primitives.
 */
export {
    GitLabPanel as GitLabView,
    GitLabPanel as default,
} from '../components/panels/GitLab/GitLabPanel';
export type { GitLabPanelProps as GitLabViewProps } from '../components/panels/GitLab/GitLabPanel';

