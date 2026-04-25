import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import type { GitLabStatePayload } from './types';

export interface GitLabState {
    data: GitLabStatePayload | null;
    hasLiveData: boolean;
}

const initialState: GitLabState = {
    data: null,
    hasLiveData: false,
};

const gitlabSlice = createSlice({
    name: 'gitlab',
    initialState,
    reducers: {
        gitlabStateReceived(state, action: PayloadAction<GitLabStatePayload>) {
            state.data = action.payload;
            state.hasLiveData = true;
        },
    },
});

export const { gitlabStateReceived } = gitlabSlice.actions;
export default gitlabSlice.reducer;
