/**
 * LogPanel — Vitest + RTL tests.
 *
 * Dispatches logLineReceived / turnTimingReceived directly (bypassing RTK
 * Query async onCacheEntryAdded) for deterministic, fast tests.
 */
import { act, fireEvent, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { installMockWsClient } from '@test/mockWsClient';
import { renderWithProviders } from '@test/renderWithProviders';
import logReducer, { logLineReceived, turnTimingReceived } from '../../../logSlice';
import { LogPanel } from '../LogPanel';
import type { LogLinePayload, TurnTimingPayload } from '../../../types';

const ws = installMockWsClient();

function makeLogLine(overrides: Partial<LogLinePayload> = {}): LogLinePayload {
    return {
        timestamp: 1700000000000,
        level: 'INFO',
        module: 'ws_server',
        message: 'Test message',
        ...overrides,
    };
}

function makeTurn(): TurnTimingPayload {
    const base = 1700000000000;
    return {
        turn_id: 'abc123',
        audio_end_ts: base,
        stt_done_ts: base + 300,
        llm_first_token_ts: base + 800,
        llm_done_ts: base + 2000,
        tts_first_audio_ts: base + 900,
        tts_done_ts: base + 2500,
    };
}

beforeEach(() => {
    ws.reset();
});

afterEach(() => {
    // restore mocks if needed
});

describe('LogPanel (compact mode)', () => {
    it('renders the Log tab by default', () => {
        renderWithProviders(<LogPanel mode="compact" />, { reducers: { log: logReducer } });
        expect(screen.getByRole('button', { name: /^Log$/i })).toBeDefined();
    });

    it('switches to Timeline tab on click', () => {
        renderWithProviders(<LogPanel mode="compact" />, { reducers: { log: logReducer } });
        fireEvent.click(screen.getByRole('button', { name: /^Timeline$/i }));
        expect(screen.getByText(/No voice turns yet/i)).toBeDefined();
    });

    it('shows waiting message when stream is empty', () => {
        renderWithProviders(<LogPanel mode="compact" />, { reducers: { log: logReducer } });
        expect(screen.getByText(/Waiting for log stream/i)).toBeDefined();
    });

    it('renders INFO log lines from WS', () => {
        const { store } = renderWithProviders(<LogPanel mode="compact" />, {
            reducers: { log: logReducer },
        });
        act(() => {
            store.dispatch(logLineReceived(makeLogLine({ message: 'System is online', level: 'INFO' })));
        });
        expect(screen.getByText('System is online')).toBeDefined();
    });

    it('renders WARNING log lines', () => {
        const { store } = renderWithProviders(<LogPanel mode="compact" />, {
            reducers: { log: logReducer },
        });
        act(() => {
            store.dispatch(logLineReceived(makeLogLine({ message: 'Low disk space', level: 'WARNING' })));
        });
        expect(screen.getByText('Low disk space')).toBeDefined();
        expect(screen.getByText('WARNING')).toBeDefined();
    });

    it('renders ERROR log lines', () => {
        const { store } = renderWithProviders(<LogPanel mode="compact" />, {
            reducers: { log: logReducer },
        });
        act(() => {
            store.dispatch(logLineReceived(makeLogLine({ message: 'Connection refused', level: 'ERROR' })));
        });
        expect(screen.getByText('Connection refused')).toBeDefined();
        expect(screen.getByText('ERROR')).toBeDefined();
    });

    it('CLEAR button dispatches logCleared', () => {
        const { store } = renderWithProviders(<LogPanel mode="compact" />, {
            reducers: { log: logReducer },
        });
        act(() => {
            store.dispatch(logLineReceived(makeLogLine()));
        });
        fireEvent.click(screen.getByRole('button', { name: /^CLEAR$/i }));
        // After clear, stream should be empty
        expect(screen.getByText(/Waiting for log stream/i)).toBeDefined();
    });

    it('timeline shows "No voice turns" when empty', () => {
        renderWithProviders(<LogPanel mode="compact" />, { reducers: { log: logReducer } });
        fireEvent.click(screen.getByRole('button', { name: /^Timeline$/i }));
        expect(screen.getByText(/No voice turns yet/i)).toBeDefined();
    });

    it('timeline renders turn data when available', () => {
        const { store } = renderWithProviders(<LogPanel mode="compact" />, {
            reducers: { log: logReducer },
        });
        act(() => {
            store.dispatch(turnTimingReceived(makeTurn()));
        });
        fireEvent.click(screen.getByRole('button', { name: /^Timeline$/i }));
        expect(screen.getByText(/abc123/i)).toBeDefined();
    });
});

describe('LogPanel (expanded mode)', () => {
    it('shows full "Log Stream" tab label in expanded mode', () => {
        renderWithProviders(<LogPanel mode="expanded" />, { reducers: { log: logReducer } });
        expect(screen.getByRole('button', { name: /Log Stream/i })).toBeDefined();
    });

    it('shows full "Turn Timeline" tab label in expanded mode', () => {
        renderWithProviders(<LogPanel mode="expanded" />, { reducers: { log: logReducer } });
        expect(screen.getByRole('button', { name: /Turn Timeline/i })).toBeDefined();
    });
});
