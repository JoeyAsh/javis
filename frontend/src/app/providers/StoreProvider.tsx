import type { ReactElement } from 'react';
import { Provider } from 'react-redux';
import { store } from '../store';
import type { StoreProviderProps } from './StoreProvider.types';

export function StoreProvider({ children }: StoreProviderProps): ReactElement {
    return <Provider store={store}>{children}</Provider>;
}

export default StoreProvider;
