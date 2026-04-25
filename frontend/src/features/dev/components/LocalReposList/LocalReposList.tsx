import type { ReactElement } from 'react';
import { repoPillClass } from '../../utils';
import { DevSectionHeader } from '../DevSectionHeader';
import type { LocalReposListProps } from './LocalReposList.types';
import styles from './LocalReposList.module.css';

export function LocalReposList({ repos }: LocalReposListProps): ReactElement {
    return (
        <>
            <DevSectionHeader label="Local Repos" />
            {repos.map((r) => (
                <div className={`list-item ${styles.row}`} key={r.id}>
                    <div className={styles.info}>
                        <div className={styles.name}>{r.name}</div>
                        <div className={styles.branch}>
                            {r.branch}
                            {r.ahead > 0 ? ` ↑${r.ahead}` : ''}
                            {r.behind > 0 ? ` ↓${r.behind}` : ''}
                            {r.uncommitted > 0 ? ` · ${r.uncommitted} files` : ''}
                        </div>
                    </div>
                    <span className={repoPillClass(r.status)}>{r.status}</span>
                </div>
            ))}
        </>
    );
}

export default LocalReposList;
