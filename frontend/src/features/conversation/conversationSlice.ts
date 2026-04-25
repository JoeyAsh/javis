import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import type { ConversationModePayload } from './types';

export interface ConversationState {
    followUpActive: boolean;
    followUpSecondsRemaining: number;
}

const initialState: ConversationState = {
    followUpActive: false,
    followUpSecondsRemaining: 0,
};

export const conversationSlice = createSlice({
    name: 'conversation',
    initialState,
    reducers: {
        conversationModeReceived(
            state,
            action: PayloadAction<Pick<ConversationModePayload, 'active' | 'seconds_remaining'>>,
        ) {
            state.followUpActive = action.payload.active;
            state.followUpSecondsRemaining = Math.max(0, action.payload.seconds_remaining);
        },
        followUpTicked(state, action: PayloadAction<number>) {
            if (state.followUpActive) {
                state.followUpSecondsRemaining = Math.max(
                    0,
                    state.followUpSecondsRemaining - action.payload,
                );
            }
        },
    },
});

export const { conversationModeReceived, followUpTicked } = conversationSlice.actions;

export default conversationSlice.reducer;
