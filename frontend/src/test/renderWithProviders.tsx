import { render } from '@testing-library/react';
import { configureStore, combineReducers } from '@reduxjs/toolkit';
import { Provider } from 'react-redux';
import { baseApi } from '@core/api/baseApi';
import { PanelAvailabilityProvider } from '@app/providers/PanelAvailabilityProvider';
import type { ReactElement, ReactNode } from 'react';
import type { RenderWithProvidersOptions } from './renderWithProviders.types';

export type { RenderWithProvidersOptions } from './renderWithProviders.types';

export function renderWithProviders(ui: ReactElement, options: RenderWithProvidersOptions = {}) {
    const { preloadedState, reducers = {}, ...renderOptions } = options;

    const store = configureStore({
        reducer: combineReducers({
            [baseApi.reducerPath]: baseApi.reducer,
            ...reducers,
        }),
        middleware: (gdm) => gdm().concat(baseApi.middleware),
        preloadedState: preloadedState as never,
    });

    const Wrapper = ({ children }: { children: ReactNode }) => (
        <Provider store={store}>
            <PanelAvailabilityProvider>{children}</PanelAvailabilityProvider>
        </Provider>
    );

    return { store, ...render(ui, { wrapper: Wrapper, ...renderOptions }) };
}
