import { baseApi } from '@core/api/baseApi';
import { wsClient } from '@core/websocket/wsClient';
import {
    orbStateReceived,
    toolCallStarted,
    toolCallFinished,
    connectionStateChanged,
} from './orbStateSlice';
import type { OrbState } from '@common/types';
import type { ToolCallPayload } from '../../types';

interface StatusMessage {
    type: string;
    state: OrbState;
}

interface ToolCallMessage {
    type: string;
    payload: ToolCallPayload;
}

export const orbStateApi = baseApi.injectEndpoints({
    endpoints: (builder) => ({
        streamOrbState: builder.query<null, void>({
            queryFn: () => ({ data: null }),
            async onCacheEntryAdded(
                _arg,
                { cacheDataLoaded, cacheEntryRemoved, dispatch },
            ) {
                await cacheDataLoaded;

                const unsubStatus = wsClient.subscribe<StatusMessage>(
                    'status',
                    (msg) => dispatch(orbStateReceived(msg.state)),
                );

                const unsubToolCall = wsClient.subscribe<ToolCallMessage>(
                    'tool_call',
                    (msg) => {
                        if (msg.payload.state === 'started') {
                            dispatch(
                                toolCallStarted({
                                    tool_name: msg.payload.tool_name,
                                    summary: msg.payload.summary,
                                }),
                            );
                        } else {
                            dispatch(toolCallFinished());
                        }
                    },
                );

                const unsubState = wsClient.onStateChange((wsState) => {
                    dispatch(connectionStateChanged(wsState === 'open'));
                });

                // Seed connected state with current wsClient state
                dispatch(connectionStateChanged(wsClient.getState() === 'open'));

                await cacheEntryRemoved;
                unsubStatus();
                unsubToolCall();
                unsubState();
            },
        }),
    }),
});

export const { useStreamOrbStateQuery } = orbStateApi;
