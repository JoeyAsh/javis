/**
 * MailPanel — panel body for mail messages.
 * Data comes from the Redux mail slice via useMail hook.
 */
import { useEffect, useRef, useState } from 'react';
import type { ReactElement } from 'react';
import { useAppSelector } from '@app';
import { selectMailSendFlashActive } from '../../mailSelectors';
import { usePanelAvailable } from '@app/providers/PanelAvailabilityProvider';
import { useMail } from '../../hooks/useMail';
import { MailCompact } from './MailCompact';
import { MailExpanded } from './MailExpanded';
import type { MailPanelProps } from './MailPanel.types';
import styles from './MailPanel.module.css';

const AVAILABILITY_TIMEOUT_MS = 10_000;

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
