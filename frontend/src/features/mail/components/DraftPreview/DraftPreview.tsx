import type { ReactElement } from 'react';
import type { DraftPreviewProps } from './DraftPreview.types';
import styles from './DraftPreview.module.css';

export function DraftPreview({ draft }: DraftPreviewProps): ReactElement {
    const preview =
        draft.body_preview.length > 80 ? `${draft.body_preview.slice(0, 80)}…` : draft.body_preview;

    return (
        <div className={styles.preview}>
            <div className={styles.label}>SENDEN — SAG &apos;JA&apos; ZUM BESTÄTIGEN</div>
            <div className={styles.to}>
                <span className={styles.fieldLabel}>AN: </span>
                {draft.to}
            </div>
            <div className={styles.subject}>
                <span className={styles.fieldLabel}>BETREFF: </span>
                {draft.subject}
            </div>
            <div className={styles.body}>{preview}</div>
        </div>
    );
}

export default DraftPreview;
