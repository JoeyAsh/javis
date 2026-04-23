/**
 * SystemPanel — Vitest + RTL tests.
 *
 * Dispatches systemMetricsReceived directly (like mail tests dispatch
 * mailStateReceived) to bypass RTK Query's async onCacheEntryAdded pipeline.
 */
import { act, screen } from '@testing-library/react';
import { describe, expect, it, beforeEach } from 'vitest';
import { installMockWsClient } from '@test/mockWsClient';
import { renderWithProviders } from '@test/renderWithProviders';
import systemReducer, { systemMetricsReceived } from '../../../systemSlice';
import { SystemPanel } from '../SystemPanel';
import type { SystemMetricsPayload } from '../../../../../types';

const ws = installMockWsClient();

const samplePayload: SystemMetricsPayload = {
    cpu: 42,
    mem: 68,
    uptime: '2d 4h',
    gpu: 31,
    cpu_temp: 62,
    net_up: 3.1,
    net_down: 12.4,
    disk: 54,
};

beforeEach(() => {
    ws.reset();
});

describe('SystemPanel — expanded mode', () => {
    it('renders tiles (mock or live) in expanded mode', () => {
        renderWithProviders(<SystemPanel mode="expanded" />, {
            reducers: { system: systemReducer },
        });
        // CPU label from mock or live tiles
        expect(screen.getAllByText('CPU').length).toBeGreaterThanOrEqual(1);
    });

    it('shows CPU value from live data after WS message', () => {
        const { store } = renderWithProviders(<SystemPanel mode="expanded" />, {
            reducers: { system: systemReducer },
        });

        act(() => {
            store.dispatch(systemMetricsReceived(samplePayload));
        });

        expect(screen.getAllByText('CPU').length).toBeGreaterThanOrEqual(1);
        // 42% from payload — toFixed(0) = "42"
        expect(screen.getByText(/42/)).toBeTruthy();
    });

    it('shows GPU tile as n/a when gpu is null', () => {
        const noGpu: SystemMetricsPayload = { ...samplePayload, gpu: null };
        const { store } = renderWithProviders(<SystemPanel mode="expanded" />, {
            reducers: { system: systemReducer },
        });

        act(() => {
            store.dispatch(systemMetricsReceived(noGpu));
        });

        expect(screen.getByText('n/a')).toBeTruthy();
    });
});

describe('SystemPanel — compact mode', () => {
    it('renders compact CPU and RAM metrics after live data', () => {
        const { store } = renderWithProviders(<SystemPanel mode="compact" />, {
            reducers: { system: systemReducer },
        });

        act(() => {
            store.dispatch(systemMetricsReceived(samplePayload));
        });

        expect(screen.getAllByText('CPU').length).toBeGreaterThanOrEqual(1);
        expect(screen.getAllByText('RAM').length).toBeGreaterThanOrEqual(1);
    });
});
