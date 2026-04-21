/**
 * MailPanel — panel body for mail messages.
 * Returns only body content; the Window wrapper supplies chrome via HudPanel.
 *
 * Prototype reference: MailPanel() in JARVIS HUD Hypermodern.html
 */
import { useEffect, useRef, useState } from 'react';
import type { ReactElement } from 'react';
import {
    subscribeEmailDraftPreviewStream,
    subscribeEmailSendDoneStream,
    subscribeMailStateStream,
} from '../../../hooks/useWebSocket';
import type { EmailDraftPreviewPayload, MailMessage, PanelMode } from '../../../types';
import { usePanelAvailable } from '../../hud/PanelAvailability';
import { MailItemRow } from './MailItemRow';
import './MailPanel.css';

/** How long to wait for a first WS payload before treating backend as unavailable. */
const AVAILABILITY_TIMEOUT_MS = 10_000;

// ---- Draft preview banner ----

export interface DraftPreviewProps {
    draft: EmailDraftPreviewPayload;
}

export function DraftPreview({ draft }: DraftPreviewProps): ReactElement {
    const preview =
        draft.body_preview.length > 80 ? `${draft.body_preview.slice(0, 80)}…` : draft.body_preview;

    return (
        <div className="mail-draft-preview">
            <div className="mail-draft-preview__label">
                SENDEN — SAG &apos;JA&apos; ZUM BESTÄTIGEN
            </div>
            <div className="mail-draft-preview__to">
                <span className="mail-draft-preview__field-label">AN: </span>
                {draft.to}
            </div>
            <div className="mail-draft-preview__subject">
                <span className="mail-draft-preview__field-label">BETREFF: </span>
                {draft.subject}
            </div>
            <div className="mail-draft-preview__body">{preview}</div>
        </div>
    );
}

// ---- Compact mode ----

interface MailCompactProps {
    messages: MailMessage[];
    unreadCount: number;
    draft: EmailDraftPreviewPayload | null;
}

function MailCompact({ messages, unreadCount, draft }: MailCompactProps): ReactElement {
    const vip = messages.filter((m) => m.isVip).length;
    const latest = messages[0];
    return (
        <div className="mail-compact">
            {draft && <DraftPreview draft={draft} />}
            <div className="mail-compact__stats">
                <span>
                    <span className="mail-compact__count">{unreadCount}</span>{' '}
                    <span className="mono-small">ungelesen</span>
                </span>
                <span style={{ color: 'var(--text-muted)' }}>·</span>
                <span>
                    <span className="mail-compact__vip">{vip}</span>{' '}
                    <span className="mono-small">VIP</span>
                </span>
            </div>
            {latest && <div className="mail-compact__sender">{latest.sender}</div>}
        </div>
    );
}

// ---- Expanded mode ----

interface MailExpandedProps {
    messages: MailMessage[];
    draft: EmailDraftPreviewPayload | null;
}

function MailExpanded({ messages, draft }: MailExpandedProps): ReactElement {
    return (
        <div className="mail-panel">
            {draft && <DraftPreview draft={draft} />}
            {messages.slice(0, 3).map((msg) => (
                <MailItemRow key={msg.id} message={msg} />
            ))}
        </div>
    );
}

// ---- Props + main export ----

export interface MailPanelProps {
    mode?: PanelMode;
}

/**
 * MailPanel body — mail messages with optional draft preview.
 * Shows empty-state when backend is live but inbox is empty.
 * Hides (returns null) when no backend payload arrives within AVAILABILITY_TIMEOUT_MS.
 */
export function MailPanel({ mode = 'expanded' }: MailPanelProps): ReactElement | null {
    const [messages, setMessages] = useState<MailMessage[]>([]);
    const [unreadCount, setUnreadCount] = useState(0);
    const [draft, setDraft] = useState<EmailDraftPreviewPayload | null>(null);
    const [hasLiveData, setHasLiveData] = useState(false);
    const [backendAvailable, setBackendAvailable] = useState(true);
    const [sendFlash, setSendFlash] = useState(false);

    usePanelAvailable('mail', backendAvailable || hasLiveData);
    const flashTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const availabilityTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    useEffect(() => {
        // If no data within timeout, treat backend as unavailable and hide panel.
        availabilityTimerRef.current = setTimeout(() => {
            setBackendAvailable(false);
        }, AVAILABILITY_TIMEOUT_MS);

        const unsubMailState = subscribeMailStateStream((payload) => {
            if (availabilityTimerRef.current) clearTimeout(availabilityTimerRef.current);
            setHasLiveData(true);
            setBackendAvailable(true);
            setMessages(payload.messages);
            setUnreadCount(payload.unread_count);
        });

        const unsubDraftPreview = subscribeEmailDraftPreviewStream((payload) => {
            setDraft(payload);
        });

        const unsubSendDone = subscribeEmailSendDoneStream((payload) => {
            setDraft(null);
            if (payload.success) {
                setSendFlash(true);
                if (flashTimerRef.current) clearTimeout(flashTimerRef.current);
                flashTimerRef.current = setTimeout(() => setSendFlash(false), 1500);
                setUnreadCount((prev) => Math.max(0, prev - 1));
            }
        });

        return () => {
            if (availabilityTimerRef.current) clearTimeout(availabilityTimerRef.current);
            if (flashTimerRef.current) clearTimeout(flashTimerRef.current);
            unsubMailState();
            unsubDraftPreview();
            unsubSendDone();
        };
    }, []);

    // Backend not available within timeout — hide the panel entirely.
    if (!backendAvailable && !hasLiveData) return null;

    const flashStyle = sendFlash
        ? { outline: '1px solid var(--accent)', transition: 'outline 300ms' }
        : {};

    // Live data arrived but inbox is empty — show empty state.
    if (hasLiveData && messages.length === 0 && !draft) {
        if (mode === 'compact') {
            return (
                <div className="mail-compact">
                    <span className="mail-empty">Keine ungelesenen E-Mails</span>
                </div>
            );
        }
        return (
            <div className="mail-panel">
                <span className="mail-empty">Keine ungelesenen E-Mails</span>
            </div>
        );
    }

    if (mode === 'compact') {
        return (
            <div style={flashStyle}>
                <MailCompact messages={messages} unreadCount={unreadCount} draft={draft} />
            </div>
        );
    }

    return (
        <div style={flashStyle}>
            <MailExpanded messages={messages} draft={draft} />
        </div>
    );
}

export default MailPanel;
