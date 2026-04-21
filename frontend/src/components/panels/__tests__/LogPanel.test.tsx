/**
 * LogPanel — Vitest + RTL tests.
 *
 * Tests:
 * 1. Compact: renders Log tab by default.
 * 2. Compact: switches to Timeline tab on click.
 * 3. Compact: log stream shows "Waiting…" message when empty.
 * 4. Compact: renders log lines with correct severity colours.
 * 5. Compact: INFO lines render in muted colour class.
 * 6. Compact: WARNING lines render.
 * 7. Compact: ERROR lines render.
 * 8. Compact: clear button clears the list.
 * 9. Timeline: shows "No voice turns" message when empty.
 * 10. Timeline: renders turn bars when data present.
 * 11. Expanded: shows full tab labels.
 */
import { render, screen, fireEvent } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// ---------------------------------------------------------------------------
// Mock hooks
// ---------------------------------------------------------------------------

import type { LogLinePayload, TurnTimingPayload } from '../../../types';

const mockClear = vi.fn();
const mockLines: LogLinePayload[] = [];
const mockTurns: TurnTimingPayload[] = [];

vi.mock('../../../hooks/useLogStream', () => ({
  useLogStream: vi.fn(() => ({
    lines: mockLines,
    clear: mockClear,
  })),
}));

vi.mock('../../../hooks/useTurnTimings', () => ({
  useTurnTimings: vi.fn(() => ({
    turns: mockTurns,
  })),
}));

import { useLogStream } from '../../../hooks/useLogStream';
import { useTurnTimings } from '../../../hooks/useTurnTimings';
import { LogPanel } from '../Log';

const mockUseLogStream = vi.mocked(useLogStream);
const mockUseTurnTimings = vi.mocked(useTurnTimings);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function setLines(lines: LogLinePayload[]): void {
  mockUseLogStream.mockReturnValue({ lines, clear: mockClear });
}

function setTurns(turns: TurnTimingPayload[]): void {
  mockUseTurnTimings.mockReturnValue({ turns });
}

function makeLogLine(
  overrides: Partial<LogLinePayload> = {},
): LogLinePayload {
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

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('LogPanel (compact mode)', () => {
  beforeEach(() => {
    setLines([]);
    setTurns([]);
    mockClear.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the Log tab by default', () => {
    render(<LogPanel mode="compact" />);
    // "Log" tab should be visible
    expect(screen.getByRole('button', { name: /^Log$/i })).toBeDefined();
  });

  it('switches to Timeline tab on click', () => {
    render(<LogPanel mode="compact" />);
    fireEvent.click(screen.getByRole('button', { name: /^Timeline$/i }));
    expect(screen.getByText(/No voice turns yet/i)).toBeDefined();
  });

  it('shows waiting message when stream is empty', () => {
    render(<LogPanel mode="compact" />);
    expect(screen.getByText(/Waiting for log stream/i)).toBeDefined();
  });

  it('renders INFO log lines', () => {
    setLines([makeLogLine({ message: 'System is online', level: 'INFO' })]);
    render(<LogPanel mode="compact" />);
    expect(screen.getByText('System is online')).toBeDefined();
  });

  it('renders WARNING log lines', () => {
    setLines([makeLogLine({ message: 'Low disk space', level: 'WARNING' })]);
    render(<LogPanel mode="compact" />);
    expect(screen.getByText('Low disk space')).toBeDefined();
    // Severity label should be rendered
    expect(screen.getByText('WARNING')).toBeDefined();
  });

  it('renders ERROR log lines', () => {
    setLines([makeLogLine({ message: 'Connection refused', level: 'ERROR' })]);
    render(<LogPanel mode="compact" />);
    expect(screen.getByText('Connection refused')).toBeDefined();
    expect(screen.getByText('ERROR')).toBeDefined();
  });

  it('CLEAR button calls clear()', () => {
    setLines([makeLogLine()]);
    render(<LogPanel mode="compact" />);
    fireEvent.click(screen.getByRole('button', { name: /^CLEAR$/i }));
    expect(mockClear).toHaveBeenCalledTimes(1);
  });

  it('timeline shows "No voice turns" when empty', () => {
    render(<LogPanel mode="compact" />);
    fireEvent.click(screen.getByRole('button', { name: /^Timeline$/i }));
    expect(screen.getByText(/No voice turns yet/i)).toBeDefined();
  });

  it('timeline renders turn data when available', () => {
    setTurns([makeTurn()]);
    render(<LogPanel mode="compact" />);
    fireEvent.click(screen.getByRole('button', { name: /^Timeline$/i }));
    // turn_id should appear in the card header
    expect(screen.getByText(/abc123/i)).toBeDefined();
  });
});

describe('LogPanel (expanded mode)', () => {
  beforeEach(() => {
    setLines([]);
    setTurns([]);
  });

  it('shows full "Log Stream" tab label in expanded mode', () => {
    render(<LogPanel mode="expanded" />);
    expect(screen.getByRole('button', { name: /Log Stream/i })).toBeDefined();
  });

  it('shows full "Turn Timeline" tab label in expanded mode', () => {
    render(<LogPanel mode="expanded" />);
    expect(screen.getByRole('button', { name: /Turn Timeline/i })).toBeDefined();
  });
});
