/**
 * useResizable — SFX-related tests (Vitest).
 *
 * Verifies:
 *   - During pointermove resize → onResizeEnd NOT called (SFX not during drag)
 *   - pointerup at end → onResizeEnd called exactly once
 *   - pointercancel → onResizeEnd called once (resize abort)
 *   - disabled → no callbacks
 */

import { render, act } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ReactElement } from 'react';
import { useResizable } from '../useResizable';

// ---------------------------------------------------------------------------
// Test component
// ---------------------------------------------------------------------------

interface TestResizeProps {
  onResize?: (w: number, h: number) => void;
  onResizing?: (w: number, h: number) => void;
  onResizeEnd?: () => void;
  disabled?: boolean;
  minW?: number;
  minH?: number;
}

function TestResizeComponent({
  onResize = vi.fn(),
  onResizing,
  onResizeEnd,
  disabled = false,
  minW = 160,
  minH = 80,
}: TestResizeProps): ReactElement {
  const getSize = vi.fn().mockReturnValue({ w: 300, h: 200 });
  const { handleRef } = useResizable<HTMLDivElement>({
    onResize,
    onResizing,
    onResizeEnd,
    getSize,
    disabled,
    minW,
    minH,
  });
  return <div data-testid="resize-handle" ref={handleRef} />;
}

// ---------------------------------------------------------------------------
// Pointer event helpers
// ---------------------------------------------------------------------------

function pointerDown(el: Element, clientX = 0, clientY = 0, pointerId = 1) {
  el.dispatchEvent(
    new PointerEvent('pointerdown', {
      bubbles: true,
      button: 0,
      pointerId,
      clientX,
      clientY,
    }),
  );
}

function pointerMove(el: Element, clientX: number, clientY: number, pointerId = 1) {
  el.dispatchEvent(
    new PointerEvent('pointermove', {
      bubbles: true,
      pointerId,
      clientX,
      clientY,
    }),
  );
}

function pointerUp(el: Element, clientX = 50, clientY = 50, pointerId = 1) {
  el.dispatchEvent(
    new PointerEvent('pointerup', {
      bubbles: true,
      pointerId,
      clientX,
      clientY,
    }),
  );
}

function pointerCancel(el: Element, pointerId = 1) {
  el.dispatchEvent(
    new PointerEvent('pointercancel', {
      bubbles: true,
      pointerId,
    }),
  );
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  HTMLDivElement.prototype.setPointerCapture = vi.fn();
  HTMLDivElement.prototype.releasePointerCapture = vi.fn();
  vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
    cb(0);
    return 0;
  });
  vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => {});
});

afterEach(() => {
  vi.clearAllMocks();
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useResizable — resize SFX NOT fired during pointermove', () => {
  it('onResizeEnd is NOT called during pointermove events', () => {
    const onResizeEnd = vi.fn();
    const { getByTestId } = render(
      <TestResizeComponent onResizeEnd={onResizeEnd} />,
    );
    const handle = getByTestId('resize-handle');

    act(() => {
      pointerDown(handle, 0, 0);
      pointerMove(handle, 50, 50);
      pointerMove(handle, 100, 80);
    });

    expect(onResizeEnd).not.toHaveBeenCalled();
  });

  it('onResizing fires during pointermove but NOT onResizeEnd', () => {
    const onResizeEnd = vi.fn();
    const onResizing = vi.fn();
    const { getByTestId } = render(
      <TestResizeComponent onResizeEnd={onResizeEnd} onResizing={onResizing} />,
    );
    const handle = getByTestId('resize-handle');

    act(() => {
      pointerDown(handle, 0, 0);
      pointerMove(handle, 50, 50);
    });

    expect(onResizing).toHaveBeenCalled();
    expect(onResizeEnd).not.toHaveBeenCalled();
  });
});

describe('useResizable — resize SFX fired on pointerup', () => {
  it('onResizeEnd is called exactly once on pointerup', () => {
    const onResizeEnd = vi.fn();
    const { getByTestId } = render(
      <TestResizeComponent onResizeEnd={onResizeEnd} />,
    );
    const handle = getByTestId('resize-handle');

    act(() => {
      pointerDown(handle, 0, 0);
      pointerMove(handle, 50, 50);
      pointerUp(handle, 50, 50);
    });

    expect(onResizeEnd).toHaveBeenCalledTimes(1);
  });

  it('onResizeEnd fires once on pointercancel (resize abort)', () => {
    const onResizeEnd = vi.fn();
    const { getByTestId } = render(
      <TestResizeComponent onResizeEnd={onResizeEnd} />,
    );
    const handle = getByTestId('resize-handle');

    act(() => {
      pointerDown(handle, 0, 0);
      pointerCancel(handle);
    });

    expect(onResizeEnd).toHaveBeenCalledTimes(1);
  });

  it('onResizeEnd is NOT called when no resize was in progress (bare pointerup)', () => {
    const onResizeEnd = vi.fn();
    const { getByTestId } = render(
      <TestResizeComponent onResizeEnd={onResizeEnd} />,
    );
    const handle = getByTestId('resize-handle');

    act(() => {
      // No preceding pointerdown
      pointerUp(handle, 0, 0);
    });

    expect(onResizeEnd).not.toHaveBeenCalled();
  });
});

describe('useResizable — onResize commit on pointerup', () => {
  it('onResize is called with w/h values on pointerup', () => {
    const onResize = vi.fn();
    const { getByTestId } = render(
      <TestResizeComponent onResize={onResize} minW={160} minH={80} />,
    );
    const handle = getByTestId('resize-handle');

    act(() => {
      pointerDown(handle, 0, 0);
      pointerMove(handle, 50, 30);
      pointerUp(handle, 50, 30);
    });

    expect(onResize).toHaveBeenCalledTimes(1);
    const [w, h] = onResize.mock.calls[0] as [number, number];
    expect(w).toBeGreaterThanOrEqual(160);
    expect(h).toBeGreaterThanOrEqual(80);
  });
});

describe('useResizable — disabled mode', () => {
  it('when disabled=true, pointerdown does NOT start resize, onResizeEnd not called', () => {
    const onResizeEnd = vi.fn();
    const { getByTestId } = render(
      <TestResizeComponent onResizeEnd={onResizeEnd} disabled={true} />,
    );
    const handle = getByTestId('resize-handle');

    act(() => {
      pointerDown(handle, 0, 0);
      pointerMove(handle, 50, 50);
      pointerUp(handle, 50, 50);
    });

    expect(onResizeEnd).not.toHaveBeenCalled();
  });
});
