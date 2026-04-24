import type { ReactElement } from 'react';
import type { PipelineRowProps } from './PipelineRow.types';
import { formatTime, pillClass, pillLabel } from './utils';
import styles from './PipelineRow.module.css';

export function PipelineRow({ pipeline }: PipelineRowProps): ReactElement {
    const timeStr = formatTime(pipeline.created_at);

    const projParts = pipeline.project.split('/');
    const projName = projParts[projParts.length - 1] ?? pipeline.project;
    const branch = projParts.length > 1 ? projParts.slice(0, -1).join('/') + '/main' : 'main';

    return (
        <div className={styles.row}>
            <span className={styles.time}>{timeStr}</span>
            <div className={styles.tx}>
                <div className={styles.proj}>
                    {projName}{' '}
                    <span className={styles.branch}>· {branch}</span>
                </div>
            </div>
            <span className={pillClass(pipeline.status)}>{pillLabel(pipeline.status)}</span>
        </div>
    );
}

export default PipelineRow;
