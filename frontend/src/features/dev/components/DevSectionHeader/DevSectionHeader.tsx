import type { ReactElement } from 'react';
import type { DevSectionHeaderProps } from './DevSectionHeader.types';
import styles from './DevSectionHeader.module.css';

export function DevSectionHeader({ label, right, stale }: DevSectionHeaderProps): ReactElement {
    return (
        <div className={styles.section}>
            <span className={styles.label}>
                {label}
                {stale === true && <span className={styles.stale}>[stale]</span>}
            </span>
            {right !== undefined && <span className={styles.right}>{right}</span>}
        </div>
    );
}

export default DevSectionHeader;
