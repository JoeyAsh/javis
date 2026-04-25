import type { MailMessage, EmailDraftPreviewPayload } from '../types';

export interface UseMailReturn {
    messages: MailMessage[];
    unreadCount: number;
    draft: EmailDraftPreviewPayload | null;
    hasLiveData: boolean;
}
