import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import type { SpotifyStatePayload } from './types';

export interface NowPlayingState {
    payload: SpotifyStatePayload | null;
    hasLiveData: boolean;
}

const initialState: NowPlayingState = {
    payload: null,
    hasLiveData: false,
};

const nowplayingSlice = createSlice({
    name: 'nowplaying',
    initialState,
    reducers: {
        spotifyStateReceived(state, action: PayloadAction<SpotifyStatePayload>) {
            state.payload = action.payload;
            state.hasLiveData = true;
        },
    },
});

export const { spotifyStateReceived } = nowplayingSlice.actions;
export default nowplayingSlice.reducer;
