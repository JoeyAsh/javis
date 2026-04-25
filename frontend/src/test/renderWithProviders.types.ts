import type { RenderOptions } from '@testing-library/react';
import type { ReducersMapObject } from '@reduxjs/toolkit';
import type { RootState } from '@app';

export interface RenderWithProvidersOptions extends Omit<RenderOptions, 'wrapper'> {
    preloadedState?: Partial<RootState>;
    /**
     * Extra slice reducers registered alongside the baseApi reducer.
     * Typically used to wire feature slices in feature-level tests.
     */
    reducers?: ReducersMapObject;
}
