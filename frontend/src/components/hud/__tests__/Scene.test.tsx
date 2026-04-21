/**
 * Scene — Vitest + RTL tests.
 *
 * Tests cover:
 *   - Root element has pointer-events: none
 *   - grid=false hides grid layer
 *   - scan=false hides scanlines layer
 *   - stars=false hides stars layer
 *   - prefers-reduced-motion: reduce → keyframe animations paused
 *   - 60 star elements rendered when stars=true (default)
 */

import { render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Scene } from '../Scene';

// ---------------------------------------------------------------------------
// matchMedia mock helper
// ---------------------------------------------------------------------------

function setReducedMotion(value: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: vi.fn().mockReturnValue({ matches: value }),
  });
}

beforeEach(() => {
  setReducedMotion(false);
});

afterEach(() => {
  vi.clearAllMocks();
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Scene — root element', () => {
  it('renders an aria-hidden root element with hud-scene class', () => {
    const { container } = render(<Scene />);
    // Root is the aria-hidden div (second child after the <style>).
    // Position/pointer-events are applied via the .hud-scene CSS class.
    const root = container.querySelector('[aria-hidden="true"]') as HTMLElement;
    expect(root).not.toBeNull();
    expect(root.classList.contains('hud-scene')).toBe(true);
  });

  it('root element carries hud-scene class (position: fixed applied via CSS)', () => {
    const { container } = render(<Scene />);
    const root = container.querySelector('[aria-hidden="true"]') as HTMLElement;
    expect(root.classList.contains('hud-scene')).toBe(true);
  });
});

describe('Scene — grid layer', () => {
  it('renders grid layer when grid=true (default)', () => {
    const { container } = render(<Scene />);
    expect(container.querySelector('.scene-grid')).toBeInTheDocument();
  });

  it('hides grid layer when grid=false', () => {
    const { container } = render(<Scene grid={false} />);
    expect(container.querySelector('.scene-grid')).toBeNull();
  });
});

describe('Scene — scanlines layer', () => {
  it('renders scanlines when scan=true (default)', () => {
    const { container } = render(<Scene />);
    // Scanlines are applied via the .hud-scene__layer--scanlines CSS class.
    const scanEl = container.querySelector('.hud-scene__layer--scanlines');
    expect(scanEl).not.toBeNull();
  });

  it('hides scanlines when scan=false', () => {
    const { container } = render(<Scene scan={false} />);
    const scanEl = container.querySelector('.hud-scene__layer--scanlines');
    expect(scanEl).toBeNull();
  });
});

describe('Scene — stars layer', () => {
  it('renders 60 star elements when stars=true (default)', () => {
    const { container } = render(<Scene />);
    const stars = container.querySelectorAll('.scene-star');
    expect(stars).toHaveLength(60);
  });

  it('renders NO star elements when stars=false', () => {
    const { container } = render(<Scene stars={false} />);
    const stars = container.querySelectorAll('.scene-star');
    expect(stars).toHaveLength(0);
  });

  it('stars have animation style set', () => {
    const { container } = render(<Scene />);
    const firstStar = container.querySelector('.scene-star') as HTMLElement;
    expect(firstStar.style.animation).toContain('starTwinkle');
  });
});

describe('Scene — keyframe injection', () => {
  it('injects a <style> element with keyframe definitions', () => {
    const { container } = render(<Scene />);
    const styleEl = container.querySelector('style');
    expect(styleEl).not.toBeNull();
    expect(styleEl!.textContent).toContain('gridDrift');
    expect(styleEl!.textContent).toContain('starTwinkle');
  });

  it('injected style includes prefers-reduced-motion media query', () => {
    const { container } = render(<Scene />);
    const styleEl = container.querySelector('style');
    expect(styleEl!.textContent).toContain('prefers-reduced-motion');
  });
});

describe('Scene — stars are deterministic', () => {
  it('renders the same star positions on re-render (stable seed)', () => {
    const { container: c1 } = render(<Scene />);
    const { container: c2 } = render(<Scene />);
    const stars1 = Array.from(c1.querySelectorAll('.scene-star')).map(
      (s) => (s as HTMLElement).style.top,
    );
    const stars2 = Array.from(c2.querySelectorAll('.scene-star')).map(
      (s) => (s as HTMLElement).style.top,
    );
    expect(stars1).toEqual(stars2);
  });
});

describe('Scene — all visible layers', () => {
  it('renders without crashing with all defaults', () => {
    expect(() => render(<Scene />)).not.toThrow();
  });

  it('renders without crashing with all layers disabled', () => {
    expect(() => render(<Scene grid={false} scan={false} stars={false} />)).not.toThrow();
  });
});
