/**
 * useDraggable — SFX-related tests (Vitest).
 *
 * Verifies:
 *   - pointerdown on handle triggers onDragStart callback
 *   - pointerup after drag triggers onDragStop callback
 *   - pointercancel during drag triggers onDragStop callback
 *   - disabled=true → no callbacks fired
 */

import { render, act } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { type ReactElement } from 'react';
import { useDraggable } from '../useDraggable';

// ---------------------------------------------------------------------------
// Test component that attaches useDraggable to a real DOM element
// ---------------------------------------------------------------------------

interface TestDragProps {
  onDragStart?: () => void;
  onDragStop?: () => void;
  onMove?: (x: number, y: number) => void;
  disabled?: boolean;
}

function TestDragComponent({
  onDragStart,
  onDragStop,
  onMove = vi.fn(),
  disabled = false,
}: TestDragProps): ReactElement {
  const getPosition = vi.fn().mockReturnValue({ x: 0, y: 0 });
  const { handleRef } = useDraggable<HTMLDivElement>({
    onMove,
    onDragStart,
    onDragStop,
    getPosition,
    disabled,
  });

  return <div data-testid="handle" ref={handleRef} />;
}

// ---------------------------------------------------------------------------
// Pointer event helpers
// ---------------------------------------------------------------------------

function pointerDown(el: Element, pointerId = 1) {
  el.dispatchEvent(
    new PointerEvent('pointerdown', {
      bubbles: true,
      button: 0,
      pointerId,
      clientX: 10,
      clientY: 10,
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

function pointerUp(el: Element, pointerId = 1) {
  el.dispatchEvent(
    new PointerEvent('pointerup', {
      bubbles: true,
      pointerId,
      clientX: 50,
      clientY: 50,
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
  // Polyfill setPointerCapture / releasePointerCapture for jsdom
  HTMLDivElement.prototype.setPointerCapture = vi.fn();
  HTMLDivElement.prototype.releasePointerCapture = vi.fn();
});

afterEach(() => {
  vi.clearAllMocks();
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useDraggable — onDragStart SFX hook point', () => {
  it('pointerdown on the handle calls onDragStart', () => {
    const onDragStart = vi.fn();
    const { getByTestId } = render(
      <TestDragComponent onDragStart={onDragStart} />,
    );
    const handle = getByTestId('handle');

    act(() => {
      pointerDown(handle);
    });

    expect(onDragStart).toHaveBeenCalledTimes(1);
  });

  it('pointerdown with right mouse button does NOT call onDragStart', () => {
    const onDragStart = vi.fn();
    const { getByTestId } = render(
      <TestDragComponent onDragStart={onDragStart} />,
    );
    const handle = getByTestId('handle');

    act(() => {
      handle.dispatchEvent(
        new PointerEvent('pointerdown', {
          bubbles: true,
          button: 2, // right click
          pointerId: 1,
        }),
      );
    });

    expect(onDragStart).not.toHaveBeenCalled();
  });
});

describe('useDraggable — onDragStop SFX hook point', () => {
  it('pointerup after drag calls onDragStop', () => {
    const onDragStop = vi.fn();
    const { getByTestId } = render(
      <TestDragComponent onDragStop={onDragStop} />,
    );
    const handle = getByTestId('handle');

    act(() => {
      pointerDown(handle);
      pointerMove(handle, 30, 30);
      pointerUp(handle);
    });

    expect(onDragStop).toHaveBeenCalledTimes(1);
  });

  it('pointercancel during drag calls onDragStop', () => {
    const onDragStop = vi.fn();
    const { getByTestId } = render(
      <TestDragComponent onDragStop={onDragStop} />,
    );
    const handle = getByTestId('handle');

    act(() => {
      pointerDown(handle);
      pointerCancel(handle);
    });

    expect(onDragStop).toHaveBeenCalledTimes(1);
  });

  it('onDragStop is NOT called when no drag is in progress (bare pointerup)', () => {
    const onDragStop = vi.fn();
    const { getByTestId } = render(
      <TestDragComponent onDragStop={onDragStop} />,
    );
    const handle = getByTestId('handle');

    act(() => {
      // No preceding pointerdown
      pointerUp(handle);
    });

    expect(onDragStop).not.toHaveBeenCalled();
  });
});

describe('useDraggable — disabled mode', () => {
  it('when disabled=true, pointerdown does NOT call onDragStart', () => {
    const onDragStart = vi.fn();
    const { getByTestId } = render(
      <TestDragComponent onDragStart={onDragStart} disabled={true} />,
    );
    const handle = getByTestId('handle');

    act(() => {
      pointerDown(handle);
    });

    expect(onDragStart).not.toHaveBeenCalled();
  });

  it('when disabled=true, pointerup does NOT call onDragStop', () => {
    const onDragStop = vi.fn();
    const { getByTestId } = render(
      <TestDragComponent onDragStop={onDragStop} disabled={true} />,
    );
    const handle = getByTestId('handle');

    act(() => {
      pointerDown(handle);
      pointerUp(handle);
    });

    expect(onDragStop).not.toHaveBeenCalled();
  });
});

describe('useDraggable — [data-no-drag] guard', () => {
  it('pointerdown on a [data-no-drag] descendant does NOT start a drag', () => {
    const onDragStart = vi.fn();
    const onMove = vi.fn();
    const getPosition = vi.fn().mockReturnValue({ x: 0, y: 0 });

    function TestWithNoDrag(): ReactElement {
      const { handleRef } = useDraggable<HTMLDivElement>({
        onMove,
        onDragStart,
        getPosition,
      });
      return (
        <div ref={handleRef} data-testid="handle">
          <button data-no-drag data-testid="noDragBtn">No drag</button>
        </div>
      );
    }

    const { getByTestId } = render(<TestWithNoDrag />);
    const noDragBtn = getByTestId('noDragBtn');

    act(() => {
      noDragBtn.dispatchEvent(
        new PointerEvent('pointerdown', {
          bubbles: true,
          button: 0,
          pointerId: 1,
          clientX: 10,
          clientY: 10,
        }),
      );
    });

    expect(onDragStart).not.toHaveBeenCalled();
  });
});
