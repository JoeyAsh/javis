import { combineReducers, configureStore } from '@reduxjs/toolkit';
import { baseApi } from '@core/api/baseApi';

export const rootReducer = combineReducers({
    [baseApi.reducerPath]: baseApi.reducer,
    // feature slices are added here as they migrate in later batches
});

export const store = configureStore({
    reducer: rootReducer,
    middleware: (getDefaultMiddleware) => getDefaultMiddleware().concat(baseApi.middleware),
    devTools: import.meta.env.DEV,
});

export type RootState = ReturnType<typeof rootReducer>;
export type AppDispatch = typeof store.dispatch;
