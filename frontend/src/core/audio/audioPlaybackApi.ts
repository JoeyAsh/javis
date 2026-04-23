/**
 * RTK Query streaming endpoint that listens for audio-related WS messages
 * and dispatches the matching audioPlayback slice actions.
 *
 * Subscribed message types:
 *   audio    — new base64 MP3 clip arrived; enqueue it.
 *   barge_in — user interrupted; flush the queue and stop playback.
 *   text     — TTS failed fallback; log only (no user-visible audio effect).
 */

import { baseApi } from '@core/api/baseApi';
import { wsClient } from '@core/websocket/wsClient';
import { audioEnqueued, bargeInRequested } from './audioPlaybackSlice';
import { orbStateReceived } from '@features/orbState/orbStateSlice';

interface AudioMessage {
    type: 'audio';
    data: string;
    channel?: string;
}

interface BargeInMessage {
    type: 'barge_in';
}

interface TextMessage {
    type: 'text';
    text: string;
}

export const audioPlaybackApi = baseApi.injectEndpoints({
    endpoints: (builder) => ({
        streamAudioPlayback: builder.query<null, void>({
            queryFn: () => ({ data: null }),
            async onCacheEntryAdded(
                _arg,
                { cacheDataLoaded, cacheEntryRemoved, dispatch },
            ) {
                await cacheDataLoaded;

                const unsubAudio = wsClient.subscribe<AudioMessage>('audio', (msg) => {
                    if (!msg.data) {
                        // TTS failed — return to idle
                        dispatch(orbStateReceived('idle'));
                        return;
                    }
                    // Ensure orb reflects speaking state while audio is enqueued
                    dispatch(orbStateReceived('speaking'));
                    const vol = msg.channel === 'backchannel' ? 0.3 : 1.0;
                    const ch: 'speech' | 'notification' | 'backchannel' =
                        msg.channel === 'backchannel'
                            ? 'backchannel'
                            : msg.channel === 'notification'
                              ? 'notification'
                              : 'speech';
                    dispatch(audioEnqueued({ data: msg.data, volume: vol, channel: ch }));
                });

                const unsubBargeIn = wsClient.subscribe<BargeInMessage>('barge_in', () => {
                    dispatch(bargeInRequested());
                    dispatch(orbStateReceived('listening'));
                });

                const unsubText = wsClient.subscribe<TextMessage>('text', (msg) => {
                    // Text-only fallback when TTS fails — log and return to idle
                    console.log('[JARVIS]', msg.text);
                    dispatch(orbStateReceived('idle'));
                });

                await cacheEntryRemoved;
                unsubAudio();
                unsubBargeIn();
                unsubText();
            },
        }),
    }),
});

export const { useStreamAudioPlaybackQuery } = audioPlaybackApi;
