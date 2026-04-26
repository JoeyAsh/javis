import { combineReducers, configureStore } from '@reduxjs/toolkit';
import { baseApi } from '@core/api/baseApi';
import { weatherApi } from '@core/api/weatherApi';
import mailReducer from '@features/mail/mailSlice';
import agendaReducer from '@features/agenda/agendaSlice';
import notificationsReducer from '@features/notifications/notificationsSlice';
import transcriptReducer from '@features/transcript/transcriptSlice';
import systemReducer from '@features/system/systemSlice';
import nowplayingReducer from '@features/nowplaying/nowplayingSlice';
import logReducer from '@features/log/logSlice';
import gitlabReducer from '@features/gitlab/gitlabSlice';
import lightsReducer from '@features/lights/lightsSlice';
import orbStateReducer from '@features/orbState/orbStateSlice';
import conversationReducer from '@features/conversation/conversationSlice';
import audioPlaybackReducer from '@core/audio/audioPlaybackSlice';
import deviceReducer from '@features/device/deviceSlice';

export const rootReducer = combineReducers({
    [baseApi.reducerPath]: baseApi.reducer,
    [weatherApi.reducerPath]: weatherApi.reducer,
    mail: mailReducer,
    agenda: agendaReducer,
    notifications: notificationsReducer,
    transcript: transcriptReducer,
    system: systemReducer,
    nowplaying: nowplayingReducer,
    log: logReducer,
    gitlab: gitlabReducer,
    lights: lightsReducer,
    orbState: orbStateReducer,
    conversation: conversationReducer,
    audioPlayback: audioPlaybackReducer,
    device: deviceReducer,
    // github has no slice — RTK Query cache only.
});

export const store = configureStore({
    reducer: rootReducer,
    middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware().concat(baseApi.middleware, weatherApi.middleware),
    devTools: import.meta.env.DEV,
});

export type RootState = ReturnType<typeof rootReducer>;
export type AppDispatch = typeof store.dispatch;
