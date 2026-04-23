import { useState } from 'react';
import type { ReactElement } from 'react';
import { Label, Mono, Button } from '@ui';
import { useGetReposQuery, useSaveReposMutation } from '../../settingsApi';
import type { ReposConfig, SaveStatus } from '../../types';
import type { RepoListProps, RepositoriesSectionProps } from './RepositoriesSection.types';

// ── RepoList sub-component ────────────────────────────────────────────────────

function RepoList({ label, repos, onAdd, onRemove, readonly = false }: RepoListProps): ReactElement {
    const [inputValue, setInputValue] = useState('');

    function handleAdd() {
        const trimmed = inputValue.trim();
        if (trimmed && !repos.includes(trimmed)) {
            onAdd(trimmed);
            setInputValue('');
        }
    }

    return (
        <div className="mb-[14px]">
            <Label className="block mb-1">{label}</Label>
            <div className="border border-border rounded-[2px] bg-black/20 px-2 py-1.5 min-h-[40px] mt-1 mb-1.5">
                {repos.length === 0 && (
                    <Mono size="sm" muted>No repositories configured.</Mono>
                )}
                {repos.map((r) => (
                    <div key={r} className="flex items-center justify-between py-0.5">
                        <Mono size="sm" secondary>{r}</Mono>
                        {!readonly && (
                            <button
                                type="button"
                                onClick={() => onRemove(r)}
                                aria-label={`Remove ${r}`}
                                className="bg-transparent border-none text-text-muted cursor-pointer font-mono text-[11px] px-1 transition-colors duration-150 hover:text-error"
                            >
                                ×
                            </button>
                        )}
                    </div>
                ))}
            </div>
            {!readonly && (
                <div className="flex gap-1.5">
                    <input
                        type="text"
                        placeholder="owner/repo"
                        value={inputValue}
                        onChange={(e) => setInputValue(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter') handleAdd(); }}
                        className="flex-1 bg-black/35 border border-border rounded-[2px] text-text font-mono text-[12px] px-2 py-[5px] outline-none"
                    />
                    <Button variant="ghost" size="sm" onClick={handleAdd}>ADD</Button>
                </div>
            )}
        </div>
    );
}

// ── RepositoriesSection ───────────────────────────────────────────────────────

export function RepositoriesSection({ initialRepos }: RepositoriesSectionProps = {}): ReactElement {
    const { data: fetchedRepos, isLoading, isError } = useGetReposQuery();
    const [saveRepos, { isLoading: isSaving, isSuccess: isSaved, isError: isSaveError }] =
        useSaveReposMutation();

    // Local optimistic state — initialised from RTK Query data once available
    const [localRepos, setLocalRepos] = useState<ReposConfig | null>(initialRepos ?? null);

    // Resolve effective repos: local override → fetched → empty fallback
    const repos: ReposConfig = localRepos ?? fetchedRepos ?? { github: [], gitlab: [] };
    const readOnly = isError;

    const saveStatus: SaveStatus = isSaving
        ? 'saving'
        : isSaved
          ? 'saved'
          : isSaveError
            ? 'error'
            : 'idle';

    async function handleSave(updated: ReposConfig) {
        setLocalRepos(updated);
        await saveRepos(updated);
    }

    function addGithub(repo: string) {
        const updated = { ...repos, github: [...repos.github, repo] };
        void handleSave(updated);
    }
    function removeGithub(repo: string) {
        const updated = { ...repos, github: repos.github.filter((r) => r !== repo) };
        void handleSave(updated);
    }
    function addGitlab(repo: string) {
        const updated = { ...repos, gitlab: [...repos.gitlab, repo] };
        void handleSave(updated);
    }
    function removeGitlab(repo: string) {
        const updated = { ...repos, gitlab: repos.gitlab.filter((r) => r !== repo) };
        void handleSave(updated);
    }

    return (
        <div className="border-b border-border pb-5 mb-5">
            <div className="flex items-center justify-between mb-[14px]">
                <Label className="text-accent text-[10px] tracking-[0.15em] uppercase">
                    Repositories
                </Label>
                {saveStatus === 'saving' && <Mono size="xs" muted>saving...</Mono>}
                {saveStatus === 'saved' && <Mono size="xs" className="text-success">saved</Mono>}
                {saveStatus === 'error' && <Mono size="xs" className="text-error">save failed</Mono>}
            </div>

            {readOnly && (
                <div className="bg-warning/8 border border-warning/25 rounded-[2px] px-2 py-1.5 mb-2.5">
                    <Mono size="sm">Backend unavailable — displaying read-only.</Mono>
                </div>
            )}

            {isLoading && !localRepos ? (
                <Mono size="sm" muted>Loading...</Mono>
            ) : (
                <>
                    <RepoList
                        label="GitHub"
                        repos={repos.github}
                        onAdd={addGithub}
                        onRemove={removeGithub}
                        readonly={readOnly}
                    />
                    <RepoList
                        label="GitLab"
                        repos={repos.gitlab}
                        onAdd={addGitlab}
                        onRemove={removeGitlab}
                        readonly={readOnly}
                    />
                </>
            )}
        </div>
    );
}

export default RepositoriesSection;
