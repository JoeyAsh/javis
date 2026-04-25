import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import type { MailMessage, MailStatePayload, EmailDraftPreviewPayload, EmailSendDonePayload } from './types';

export interface MailState {
    messages: MailMessage[];
    unreadCount: number;
    draft: EmailDraftPreviewPayload | null;
    hasLiveData: boolean;
    lastSendSucceeded: boolean;
    sendFlashAt: number | null;
}

const initialState: MailState = {
    messages: [],
    unreadCount: 0,
    draft: null,
    hasLiveData: false,
    lastSendSucceeded: false,
    sendFlashAt: null,
};

const mailSlice = createSlice({
    name: 'mail',
    initialState,
    reducers: {
        mailStateReceived(state, action: PayloadAction<MailStatePayload>) {
            state.messages = action.payload.messages;
            state.unreadCount = action.payload.unread_count;
            state.hasLiveData = true;
        },
        draftPreviewReceived(state, action: PayloadAction<EmailDraftPreviewPayload>) {
            state.draft = action.payload;
        },
        emailSendDone: {
            reducer(
                state,
                action: PayloadAction<{ payload: EmailSendDonePayload; timestamp: number }>,
            ) {
                state.draft = null;
                if (action.payload.payload.success) {
                    state.lastSendSucceeded = true;
                    state.sendFlashAt = action.payload.timestamp;
                    state.unreadCount = Math.max(0, state.unreadCount - 1);
                } else {
                    state.lastSendSucceeded = false;
                }
            },
            prepare(payload: EmailSendDonePayload) {
                return { payload: { payload, timestamp: Date.now() } };
            },
        },
    },
});

export const { mailStateReceived, draftPreviewReceived, emailSendDone } = mailSlice.actions;
export default mailSlice.reducer;
