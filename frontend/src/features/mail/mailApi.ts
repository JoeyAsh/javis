import { baseApi } from '@core/api/baseApi';
import { wsClient } from '@core/websocket/wsClient';
import { mailStateReceived, draftPreviewReceived, emailSendDone } from './mailSlice';
import type { MailStatePayload, EmailDraftPreviewPayload, EmailSendDonePayload } from './types';

export const mailApi = baseApi.injectEndpoints({
    endpoints: (builder) => ({
        streamMail: builder.query<null, void>({
            queryFn: () => ({ data: null }),
            async onCacheEntryAdded(_arg, { cacheDataLoaded, cacheEntryRemoved, dispatch }) {
                await cacheDataLoaded;

                const unsubs = [
                    wsClient.subscribe<{ type: string; payload: MailStatePayload }>(
                        'mail_state',
                        (msg) => dispatch(mailStateReceived(msg.payload)),
                    ),
                    wsClient.subscribe<{ type: string; payload: EmailDraftPreviewPayload }>(
                        'email_draft_preview',
                        (msg) => dispatch(draftPreviewReceived(msg.payload)),
                    ),
                    wsClient.subscribe<{ type: string; payload: EmailSendDonePayload }>(
                        'email_send_done',
                        (msg) => dispatch(emailSendDone(msg.payload)),
                    ),
                ];

                await cacheEntryRemoved;
                unsubs.forEach((u) => u());
            },
        }),
    }),
});

export const { useStreamMailQuery } = mailApi;
