import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import type {
    AgendaEvent,
    CalendarStatePayload,
    CalendarOpPreviewPayload,
    CalendarOpDonePayload,
} from './types';

export interface AgendaState {
    events: AgendaEvent[];
    hasLiveData: boolean;
    pendingOp: CalendarOpPreviewPayload | null;
}

const initialState: AgendaState = {
    events: [],
    hasLiveData: false,
    pendingOp: null,
};

const agendaSlice = createSlice({
    name: 'agenda',
    initialState,
    reducers: {
        calendarStateReceived(state, action: PayloadAction<CalendarStatePayload>) {
            state.events = action.payload.events;
            state.hasLiveData = true;
        },
        calendarOpPreviewReceived(state, action: PayloadAction<CalendarOpPreviewPayload>) {
            state.pendingOp = action.payload;
        },
        calendarOpDone(state, action: PayloadAction<CalendarOpDonePayload>) {
            if (action.payload.success) {
                state.pendingOp = null;
            }
        },
    },
});

export const { calendarStateReceived, calendarOpPreviewReceived, calendarOpDone } =
    agendaSlice.actions;
export default agendaSlice.reducer;
