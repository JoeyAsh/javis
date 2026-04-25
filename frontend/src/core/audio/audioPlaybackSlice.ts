import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';

export interface AudioChannel {
    data: string;
    volume: number;
    channel: 'speech' | 'notification' | 'backchannel';
}

export interface AudioPlaybackState {
    queue: AudioChannel[];
    isPlaying: boolean;
    /**
     * Increments every time a barge_in flush is requested.
     * The playback hook watches this value; when it changes the hook
     * calls its local stopAll() and discards any queued audio.
     */
    pendingFlushId: number;
}

const initialState: AudioPlaybackState = {
    queue: [],
    isPlaying: false,
    pendingFlushId: 0,
};

export const audioPlaybackSlice = createSlice({
    name: 'audioPlayback',
    initialState,
    reducers: {
        audioEnqueued(state, action: PayloadAction<AudioChannel>) {
            state.queue.push(action.payload);
        },
        audioConsumed(state) {
            state.queue = state.queue.slice(1);
        },
        playingChanged(state, action: PayloadAction<boolean>) {
            state.isPlaying = action.payload;
        },
        bargeInRequested(state) {
            state.pendingFlushId += 1;
            // Keep the first (currently-playing) item so the hook can stop it;
            // the hook's stopAll() will clear everything immediately.
            state.queue = [];
        },
    },
});

export const {
    audioEnqueued,
    audioConsumed,
    playingChanged,
    bargeInRequested,
} = audioPlaybackSlice.actions;

export default audioPlaybackSlice.reducer;
