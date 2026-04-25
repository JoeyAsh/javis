import type { RootState } from '@app';
import type { MailMessage, EmailDraftPreviewPayload } from './types';

export function selectMailMessages(state: RootState): MailMessage[] {
    return state.mail.messages;
}

export function selectMailUnreadCount(state: RootState): number {
    return state.mail.unreadCount;
}

export function selectMailDraft(state: RootState): EmailDraftPreviewPayload | null {
    return state.mail.draft;
}

export function selectMailHasLiveData(state: RootState): boolean {
    return state.mail.hasLiveData;
}

export function selectMailSendFlashActive(state: RootState, now: number): boolean {
    const { sendFlashAt } = state.mail;
    if (sendFlashAt === null) return false;
    return now - sendFlashAt < 1500;
}
