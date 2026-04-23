/**
 * MailPanel — panel body for mail messages.
 * Data comes from the Redux mail slice via useMail hook.
 */
import { useEffect, useRef, useState } from 'react';
import type { ReactElement } from 'react';
import { useAppSelector } from '@app';
import { selectMailSendFlashActive } from '../../mailSelectors';
import { usePanelAvailable } from '../../../../contexts/PanelAvailability';
import { useMail } from '../../hooks/useMail';
import { DraftPreview } from '../DraftPreview';
import { MailItemRow } from '../MailItemRow';
import type { MailPanelProps } from './MailPanel.types';
import type { MailMessage, EmailDraftPreviewPayload } from '../../types';
import styles from './MailPanel.module.css';

const AVAILABILITY_TIMEOUT_MS = 10_000;

// ---- Compact mode ----

type MailCompactProps = {
    messages: MailMessage[];
    unreadCount: number;
    draft: EmailDraftPreviewPayload | null;
    sendFlash: boolean;
};

function MailCompact({ messages, unreadCount, draft, sendFlash }: MailCompactProps): ReactElement {
    const vip = messages.filter((m) => m.isVip).length;
    const latest = messages[0];
    return (
        <div className={`${styles.compact}${sendFlash ? ` ${styles.flash}` : ''}`}>
            {draft && <DraftPreview draft={draft} />}
            <div className={styles.stats}>
                <span>
                    <span className={styles.count}>{unreadCount}</span>{' '}
                    <span className={styles.monoSmall}>ungelesen</span>
                </span>
                <span className={styles.separator}>·</span>
                <span>
                    <span className={styles.vip}>{vip}</span>{' '}
                    <span className={styles.monoSmall}>VIP</span>
                </span>
            </div>
            {latest && <div className={styles.sender}>{latest.sender}</div>}
        </div>
    );
}

// ---- Expanded mode ----

type MailExpandedProps = {
    messages: MailMessage[];
    draft: EmailDraftPreviewPayload | null;
    sendFlash: boolean;
}

function MailExpanded({ messages, draft, sendFlash }: MailExpandedProps): ReactElement {
    return (
        <div className={`${styles.panel}${sendFlash ? ` ${styles.flash}` : ''}`}>
            {draft && <DraftPreview draft={draft} />}
            {messages.slice(0, 3).map((msg) => (
                <MailItemRow key={msg.id} message={msg} />
            ))}
        </div>
    );
}

// ---- Main export ----

/**
 * MailPanel — renders mail messages with draft preview.
 * Shows empty-state when backend is live but inbox is empty.
 * Shows unavailable-state if no payload arrives within 10 s.
 */
export function MailPanel({ mode = 'expanded' }: MailPanelProps): ReactElement {
    const { messages, unreadCount, draft, hasLiveData } = useMail();
    const [backendAvailable, setBackendAvailable] = useState(true);
    const availabilityTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    // Send-flash: selector computes within-1500ms window from Redux state.
    const sendFlash = useAppSelector((state) => selectMailSendFlashActive(state, Date.now()));

    usePanelAvailable('mail', backendAvailable || hasLiveData);

    useEffect(() => {
        availabilityTimerRef.current = setTimeout(() => {
            setBackendAvailable(false);
        }, AVAILABILITY_TIMEOUT_MS);

        return () => {
            if (availabilityTimerRef.current) clearTimeout(availabilityTimerRef.current);
        };
    }, []);

    // Cancel availability timer once live data arrives.
    useEffect(() => {
        if (hasLiveData && availabilityTimerRef.current) {
            clearTimeout(availabilityTimerRef.current);
            availabilityTimerRef.current = null;
            setBackendAvailable(true);
        }
    }, [hasLiveData]);

    // Backend not available within timeout — show fallback.
    if (!backendAvailable && !hasLiveData) {
        return (
            <div className={styles.panel}>
                <span className={styles.empty}>Postfach momentan nicht erreichbar</span>
            </div>
        );
    }

    // Live data but inbox is empty.
    if (hasLiveData && messages.length === 0 && !draft) {
        if (mode === 'compact') {
            return (
                <div className={styles.compact}>
                    <span className={styles.empty}>Keine ungelesenen E-Mails</span>
                </div>
            );
        }
        return (
            <div className={styles.panel}>
                <span className={styles.empty}>Keine ungelesenen E-Mails</span>
            </div>
        );
    }

    if (mode === 'compact') {
        return (
            <MailCompact
                messages={messages}
                unreadCount={unreadCount}
                draft={draft}
                sendFlash={sendFlash}
            />
        );
    }

    return <MailExpanded messages={messages} draft={draft} sendFlash={sendFlash} />;
}

export default MailPanel;
