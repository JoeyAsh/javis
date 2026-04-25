import type { ReactElement } from 'react';
import { DevSectionHeader } from '../DevSectionHeader';
import type { DockerContainersListProps } from './DockerContainersList.types';
import { containerPillClass } from './utils';
import styles from './DockerContainersList.module.css';

export function DockerContainersList({ containers }: DockerContainersListProps): ReactElement {
    return (
        <>
            <DevSectionHeader label="Docker" right={`${containers.length} containers`} />
            {containers.map((c) => (
                <div className={`list-item ${styles.row}`} key={c.id}>
                    <div className={styles.nameRow}>
                        <span
                            className={`${styles.name} ${c.status === 'running' ? styles.nameRunning : styles.nameStopped}`}
                        >
                            {c.name}
                        </span>
                        <span className={containerPillClass(c.status)}>{c.status}</span>
                    </div>
                    <div className={styles.barRow}>
                        <span className={styles.barLabel}>CPU</span>
                        <div className={styles.barTrack}>
                            <div className={styles.barFillCpu} style={{ width: `${c.cpu}%` }} />
                        </div>
                        <span className={styles.barValue}>{c.cpu}%</span>
                    </div>
                    <div className={styles.barRow}>
                        <span className={styles.barLabel}>MEM</span>
                        <div className={styles.barTrack}>
                            <div className={styles.barFillMem} style={{ width: `${c.mem}%` }} />
                        </div>
                        <span className={styles.barValue}>{c.mem}%</span>
                    </div>
                </div>
            ))}
        </>
    );
}

export default DockerContainersList;
