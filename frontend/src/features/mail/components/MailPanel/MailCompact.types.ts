import type { MailMessage, EmailDraftPreviewPayload } from '../../types';

export interface MailCompactProps {
    messages: MailMessage[];
    unreadCount: number;
    draft: EmailDraftPreviewPayload | null;
    sendFlash: boolean;
}
