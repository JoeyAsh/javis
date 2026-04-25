import type { ReposConfig } from '../../types';

export interface RepoListProps {
    label: string;
    repos: string[];
    onAdd: (repo: string) => void;
    onRemove: (repo: string) => void;
    readonly?: boolean;
}

/** Exposed for tests */
export interface RepositoriesSectionProps {
    /** Optional initial repos override (used in unit tests to skip RTK Query) */
    initialRepos?: ReposConfig;
}
