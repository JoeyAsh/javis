/**
 * Window — SFX integration tests (Vitest + RTL).
 *
 * Verifies that:
 *   - Pin button click → playOneShot('pin') or ('unpin')
 *   - Drag SFX callbacks are wired (drag_start / drag_end)
 *   - Resize handle is present in the DOM
 *   - HudPanel chrome is present inside Window
 *   - window title and control buttons are present
 */

import { render, screen, fireEvent, act } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { PanelId } from '../../../types';
import type { WindowState, WindowMap } from '../WindowManager';
import type { SlotId, SlotRect } from '../SlotGrid';

// ---------------------------------------------------------------------------
// Mock WindowManager — return controllable state
// ---------------------------------------------------------------------------

const mockFocus = vi.fn();
const mockMaximize = vi.fn();
const mockMinimize = vi.fn();
const mockToggleMaximize = vi.fn();
const mockMove = vi.fn();
const mockResize = vi.fn();
const mockResetWindow = vi.fn();
const mockSetActiveSnap = vi.fn();
const mockSnapWindow = vi.fn();

function buildSlotRects(): Record<SlotId, SlotRect> {
  const rect: SlotRect = { x: 12, y: 48, w: 280, h: 200 };
  return {
    L1: rect,
    L2: { ...rect, y: 260 },
    L3: { ...rect, y: 472 },
    R1: { ...rect, x: 700 },
    R2: { ...rect, x: 700, y: 260 },
    R3: { ...rect, x: 700, y: 472 },
    B1: { ...rect, x: 12, y: 700, w: 180, h: 140 },
    B2: { ...rect, x: 200, y: 700, w: 180, h: 140 },
    B3: { ...rect, x: 388, y: 700, w: 180, h: 140 },
  };
}

let currentWindowState: WindowState = {
  id: 'agenda' as PanelId,
  homeSlotId: 'L1' as SlotId,
  maximized: false,
  floatingRect: null,
  zIndex: 10,
  visible: true,
};

vi.mock('../WindowManager', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../WindowManager')>();
  return {
    ...actual,
    useWindowManager: () => ({
      windows: { agenda: currentWindowState } as WindowMap,
      focusedId: 'agenda' as PanelId,
      activeSnap: null,
      settlingIds: new Set<PanelId>(),
      slotRects: buildSlotRects(),
      focus: mockFocus,
      clearFocus: vi.fn(),
      maximize: mockMaximize,
      minimize: mockMinimize,
      toggleMaximize: mockToggleMaximize,
      move: mockMove,
      resize: mockResize,
      setActiveSnap: mockSetActiveSnap,
      snapWindow: mockSnapWindow,
      swapSlots: vi.fn(),
      resetWindow: mockResetWindow,
      resetAll: vi.fn(),
    }),
  };
});

// ---------------------------------------------------------------------------
// Mock drag/resize/swapDrag hooks
// ---------------------------------------------------------------------------

let capturedDragStart: (() => void) | undefined;
let capturedDragStop: (() => void) | undefined;

vi.mock('../../../hooks/useDraggable', () => ({
  useDraggable: vi.fn().mockImplementation(
    ({ onDragStart, onDragStop }: {
      onDragStart?: () => void;
      onDragStop?: () => void;
    }) => {
      capturedDragStart = onDragStart;
      capturedDragStop = onDragStop;
      return { handleRef: { current: null }, isDragging: () => false };
    },
  ),
}));

vi.mock('../../../hooks/useResizable', () => ({
  useResizable: vi.fn().mockImplementation(() => ({
    handleRef: { current: null },
    isResizing: () => false,
  })),
}));

vi.mock('../../../hooks/useSwapDrag', () => ({
  useSwapDrag: vi.fn().mockImplementation(() => ({
    handleRef: { current: null },
  })),
}));

// ---------------------------------------------------------------------------
// SfxContext mock
// ---------------------------------------------------------------------------

const mockPlayOneShot = vi.fn();

vi.mock('../../../hud/SfxContext', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../hud/SfxContext')>();
  return {
    ...actual,
    useSfx: () => ({ playOneShot: mockPlayOneShot }),
  };
});

// ---------------------------------------------------------------------------
// Static import (after all mocks registered)
// ---------------------------------------------------------------------------

import { Window } from '../Window';

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.spyOn(Storage.prototype, 'getItem').mockReturnValue(null);
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {});
  vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {});
  currentWindowState = {
    id: 'agenda' as PanelId,
    homeSlotId: 'L1' as SlotId,
    maximized: false,
    floatingRect: null,
    zIndex: 10,
    visible: true,
  };
  capturedDragStart = undefined;
  capturedDragStop = undefined;
});

afterEach(() => {
  vi.clearAllMocks();
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Render helper
// ---------------------------------------------------------------------------

function renderWindow(overrides: Partial<{ disabled: boolean }> = {}) {
  return render(
    <Window
      id={'agenda' as PanelId}
      title="Agenda"
      disabled={overrides.disabled}
    >
      {() => <div>body content</div>}
    </Window>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Window — HudPanel chrome', () => {
  it('renders HudPanel with corner brackets inside the window', () => {
    const { container } = renderWindow();
    expect(container.querySelector('.hud-corner-brackets')).toBeInTheDocument();
  });

  it('renders the bloom overlay inside the window', () => {
    const { container } = renderWindow();
    expect(container.querySelector('.hud-bloom')).toBeInTheDocument();
  });

  it('renders light trace strips inside the window', () => {
    const { container } = renderWindow();
    expect(container.querySelectorAll('.hud-trace').length).toBeGreaterThanOrEqual(4);
  });
});

describe('Window — structural elements', () => {
  it('renders the window title in the header', () => {
    renderWindow();
    expect(screen.getByText('Agenda')).toBeInTheDocument();
  });

  it('renders a maximize button', () => {
    renderWindow();
    expect(
      screen.getByRole('button', { name: /maximize window/i }),
    ).toBeInTheDocument();
  });

  it('renders a reset position button', () => {
    renderWindow();
    expect(
      screen.getByRole('button', { name: /reset window position/i }),
    ).toBeInTheDocument();
  });

  it('renders a pin button', () => {
    renderWindow();
    expect(screen.getByRole('button', { name: /pin window/i })).toBeInTheDocument();
  });

  it('renders the resize handle element', () => {
    const { container } = renderWindow();
    expect(container.querySelector('.window-resize')).toBeInTheDocument();
  });

  it('renders children body content', () => {
    renderWindow();
    expect(screen.getByText('body content')).toBeInTheDocument();
  });

  it('window root has role=dialog with aria-label equal to title', () => {
    renderWindow();
    expect(screen.getByRole('dialog', { name: 'Agenda' })).toBeInTheDocument();
  });
});

describe('Window — hidden state', () => {
  it('renders nothing when visible=false', () => {
    currentWindowState = { ...currentWindowState, visible: false };
    const { container } = renderWindow();
    expect(container.querySelector('.window')).toBeNull();
  });
});

describe('Window — pin SFX', () => {
  it('clicking pin button fires playOneShot("pin")', () => {
    renderWindow();
    // Simulate a pointer event on the dialog so the SFX guard timestamp is set
    act(() => {
      screen.getByRole('dialog').dispatchEvent(
        new PointerEvent('pointerdown', { bubbles: true }),
      );
    });
    fireEvent.click(screen.getByRole('button', { name: /pin window/i }));
    expect(mockPlayOneShot).toHaveBeenCalledWith('pin');
  });

  it('clicking unpin fires playOneShot("unpin") after first pin', () => {
    renderWindow();
    // Pin it first
    act(() => {
      screen.getByRole('dialog').dispatchEvent(
        new PointerEvent('pointerdown', { bubbles: true }),
      );
    });
    fireEvent.click(screen.getByRole('button', { name: /pin window/i }));
    vi.clearAllMocks();

    // Now unpin
    act(() => {
      screen.getByRole('dialog').dispatchEvent(
        new PointerEvent('pointerdown', { bubbles: true }),
      );
    });
    fireEvent.click(screen.getByRole('button', { name: /unpin window/i }));
    expect(mockPlayOneShot).toHaveBeenCalledWith('unpin');
  });
});

describe('Window — drag SFX callbacks', () => {
  it('onDragStart callback fires drag_start SFX when invoked', () => {
    renderWindow();
    expect(capturedDragStart).toBeDefined();
    capturedDragStart!();
    expect(mockPlayOneShot).toHaveBeenCalledWith('drag_start');
  });

  it('onDragStop callback fires drag_end SFX when invoked', () => {
    renderWindow();
    expect(capturedDragStop).toBeDefined();
    capturedDragStop!();
    expect(mockPlayOneShot).toHaveBeenCalledWith('drag_end');
  });
});
