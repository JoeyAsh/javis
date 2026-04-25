import type { ReactElement } from 'react';
import { DraftPreview } from '../DraftPreview';
import { MailItemRow } from '../MailItemRow';
import type { MailExpandedProps } from './MailExpanded.types';
import styles from './MailPanel.module.css';

export function MailExpanded({ messages, draft, sendFlash }: MailExpandedProps): ReactElement {
    return (
        <div className={`${styles.panel}${sendFlash ? ` ${styles.flash}` : ''}`}>
            {draft && <DraftPreview draft={draft} />}
            {messages.slice(0, 3).map((msg) => (
                <MailItemRow key={msg.id} message={msg} />
            ))}
        </div>
    );
}

export default MailExpanded;
