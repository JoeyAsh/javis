import type { MailMessage, EmailDraftPreviewPayload } from '../../types';

export interface MailExpandedProps {
    messages: MailMessage[];
    draft: EmailDraftPreviewPayload | null;
    sendFlash: boolean;
}
