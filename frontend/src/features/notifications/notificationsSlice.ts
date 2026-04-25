import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import type { HudNotification, NotificationPayload } from './types';

const MAX_NOTIFICATIONS = 20;

export interface NotificationsState {
    items: HudNotification[];
    hasLiveData: boolean;
}

const initialState: NotificationsState = {
    items: [],
    hasLiveData: false,
};

const notificationsSlice = createSlice({
    name: 'notifications',
    initialState,
    reducers: {
        notificationReceived(state, action: PayloadAction<NotificationPayload>) {
            state.hasLiveData = true;
            const payload = action.payload;
            const next: HudNotification = {
                id: payload.id,
                severity: payload.severity,
                title: payload.title,
                detail: payload.detail ?? '',
                timestamp: payload.timestamp ?? new Date().toISOString(),
            };
            // Dedup by id, prepend (newest first), cap at 20.
            const filtered = state.items.filter((n) => n.id !== next.id);
            const combined = [next, ...filtered];
            state.items = combined.length > MAX_NOTIFICATIONS
                ? combined.slice(0, MAX_NOTIFICATIONS)
                : combined;
        },
    },
});

export const { notificationReceived } = notificationsSlice.actions;
export default notificationsSlice.reducer;
