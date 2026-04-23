import { baseApi } from '@core/api/baseApi';
import { wsClient } from '@core/websocket/wsClient';
import { calendarStateReceived, calendarOpPreviewReceived, calendarOpDone } from './agendaSlice';
import type {
    CalendarStatePayload,
    CalendarOpPreviewPayload,
    CalendarOpDonePayload,
} from './types';

export const agendaApi = baseApi.injectEndpoints({
    endpoints: (builder) => ({
        streamAgenda: builder.query<null, void>({
            queryFn: () => ({ data: null }),
            async onCacheEntryAdded(_arg, { cacheDataLoaded, cacheEntryRemoved, dispatch }) {
                await cacheDataLoaded;

                const unsubs = [
                    wsClient.subscribe<{ type: string; payload: CalendarStatePayload }>(
                        'calendar_state',
                        (msg) => dispatch(calendarStateReceived(msg.payload)),
                    ),
                    wsClient.subscribe<{ type: string; payload: CalendarOpPreviewPayload }>(
                        'calendar_op_preview',
                        (msg) => dispatch(calendarOpPreviewReceived(msg.payload)),
                    ),
                    wsClient.subscribe<{ type: string; payload: CalendarOpDonePayload }>(
                        'calendar_op_done',
                        (msg) => dispatch(calendarOpDone(msg.payload)),
                    ),
                ];

                await cacheEntryRemoved;
                unsubs.forEach((u) => u());
            },
        }),
    }),
});

export const { useStreamAgendaQuery } = agendaApi;
