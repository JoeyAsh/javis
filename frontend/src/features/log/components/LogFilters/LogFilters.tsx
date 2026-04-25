import type { ReactElement } from 'react';
import type { LogFiltersProps } from './LogFilters.types';
import styles from './LogFilters.module.css';

export function LogFilters({ lineCount, paused = false, onClear }: LogFiltersProps): ReactElement {
    return (
        <div className={styles.toolbar}>
            <span className={styles.count}>
                {lineCount} lines{paused ? ' — paused' : ''}
            </span>
            <button type="button" className={styles.clearBtn} onClick={onClear}>
                CLEAR
            </button>
        </div>
    );
}

export default LogFilters;
