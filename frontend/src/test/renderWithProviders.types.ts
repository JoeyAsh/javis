import type { RenderOptions } from '@testing-library/react';
import type { RootState } from '@app';

export interface RenderWithProvidersOptions extends Omit<RenderOptions, 'wrapper'> {
    preloadedState?: Partial<RootState>;
}
