/**
 * MailItemRow — single mail message list item.
 * Matches prototype `.ev` pattern for MailPanel.
 */
import type { ReactElement } from 'react';
import { useSfx } from '../../../hud/SfxContext';
import type { MailMessage } from '../../../types';
import './MailPanel.css';

function relativeTime(iso: string): string {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60_000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h`;
    return `${Math.floor(hrs / 24)}d`;
}

export interface MailItemRowProps {
    message: MailMessage;
    onClick?: (message: MailMessage) => void;
}

export function MailItemRow({ message, onClick }: MailItemRowProps): ReactElement {
    const { playOneShot } = useSfx();

    const handleClick = (): void => {
        playOneShot('click');
        onClick?.(message);
    };

    const timeClass = message.unread
        ? 'mail-item-row__time mail-item-row__time--unread'
        : 'mail-item-row__time mail-item-row__time--read';

    return (
        <div
            className="mail-item-row"
            onClick={handleClick}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') handleClick();
            }}
        >
            <span className={timeClass}>{relativeTime(message.receivedAt)}</span>
            <div className="mail-item-row__body">
                <div className="mail-item-row__subject">{message.subject}</div>
                <div className="mail-item-row__sender">{message.sender}</div>
            </div>
            {message.unread && <span className="mail-item-row__pill">NEU</span>}
        </div>
    );
}

export default MailItemRow;
