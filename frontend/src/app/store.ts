import { combineReducers, configureStore } from '@reduxjs/toolkit';
import { baseApi } from '@core/api/baseApi';
import mailReducer from '@features/mail/mailSlice';
import agendaReducer from '@features/agenda/agendaSlice';
import notificationsReducer from '@features/notifications/notificationsSlice';
import transcriptReducer from '@features/transcript/transcriptSlice';

export const rootReducer = combineReducers({
    [baseApi.reducerPath]: baseApi.reducer,
    mail: mailReducer,
    agenda: agendaReducer,
    notifications: notificationsReducer,
    transcript: transcriptReducer,
});

export const store = configureStore({
    reducer: rootReducer,
    middleware: (getDefaultMiddleware) => getDefaultMiddleware().concat(baseApi.middleware),
    devTools: import.meta.env.DEV,
});

export type RootState = ReturnType<typeof rootReducer>;
export type AppDispatch = typeof store.dispatch;
