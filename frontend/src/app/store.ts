import { combineReducers, configureStore } from '@reduxjs/toolkit';
import { baseApi } from '@core/api/baseApi';
import mailReducer from '@features/mail/mailSlice';
import agendaReducer from '@features/agenda/agendaSlice';
import notificationsReducer from '@features/notifications/notificationsSlice';
import transcriptReducer from '@features/transcript/transcriptSlice';
import systemReducer from '@features/system/systemSlice';
import nowplayingReducer from '@features/nowplaying/nowplayingSlice';
import logReducer from '@features/log/logSlice';
import gitlabReducer from '@features/gitlab/gitlabSlice';
import lightsReducer from '@features/lights/lightsSlice';

export const rootReducer = combineReducers({
    [baseApi.reducerPath]: baseApi.reducer,
    mail: mailReducer,
    agenda: agendaReducer,
    notifications: notificationsReducer,
    transcript: transcriptReducer,
    system: systemReducer,
    nowplaying: nowplayingReducer,
    log: logReducer,
    gitlab: gitlabReducer,
    lights: lightsReducer,
    // github has no slice — RTK Query cache only.
});

export const store = configureStore({
    reducer: rootReducer,
    middleware: (getDefaultMiddleware) => getDefaultMiddleware().concat(baseApi.middleware),
    devTools: import.meta.env.DEV,
});

export type RootState = ReturnType<typeof rootReducer>;
export type AppDispatch = typeof store.dispatch;
