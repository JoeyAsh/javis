/**
 * HudPanel — Vitest + RTL tests.
 *
 * Tests cover:
 *   - Renders children in content slot
 *   - Renders header slot when provided
 *   - Renders badge slot when provided
 *   - focused prop toggles focused class on root
 *   - Corner brackets (tl/tr/bl/br) present in DOM
 *   - Light trace strips (4) present in DOM
 *   - Bloom overlay present in DOM
 *   - variant='dev' applies correct class
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { HudPanel } from '../HudPanel';

// ---------------------------------------------------------------------------
// Note: hud.css is imported inside HudPanel — Vitest/jsdom ignores CSS files
// by default (no style computation), but imports succeed. If the import fails,
// add a CSS mock to vite.config.ts.
// ---------------------------------------------------------------------------

describe('HudPanel — children (content slot)', () => {
  it('renders children inside the panel', () => {
    render(<HudPanel><span>Panel body</span></HudPanel>);
    expect(screen.getByText('Panel body')).toBeInTheDocument();
  });

  it('renders nothing in content area when no children passed', () => {
    const { container } = render(<HudPanel />);
    // Should not crash and the panel root should exist
    expect(container.firstChild).toBeInTheDocument();
  });
});

describe('HudPanel — header slot', () => {
  it('renders header content when title prop is provided', () => {
    render(<HudPanel title={<span>Window Title</span>} />);
    expect(screen.getByText('Window Title')).toBeInTheDocument();
  });

  it('does NOT render header row when neither title nor badge nor actions is provided', () => {
    const { container } = render(<HudPanel />);
    // The header bar row carries the .hud-panel__header--bar class when rendered.
    const headerEl = container.querySelector('.hud-panel__header--bar');
    expect(headerEl).toBeNull();
  });
});

describe('HudPanel — badge slot', () => {
  it('renders badge content when badge prop is provided', () => {
    render(<HudPanel badge={<span>LIVE</span>} />);
    expect(screen.getByText('LIVE')).toBeInTheDocument();
  });

  it('renders both title and badge when both are provided', () => {
    render(
      <HudPanel
        title={<span>Title</span>}
        badge={<span>Status</span>}
      />,
    );
    expect(screen.getByText('Title')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();
  });
});

describe('HudPanel — focused prop', () => {
  it('adds hud-panel--focused class when focused=true', () => {
    const { container } = render(<HudPanel focused />);
    expect(container.firstChild).toHaveClass('hud-panel--focused');
  });

  it('does NOT add hud-panel--focused class when focused=false (default)', () => {
    const { container } = render(<HudPanel />);
    expect(container.firstChild).not.toHaveClass('hud-panel--focused');
  });
});

describe('HudPanel — variant prop', () => {
  it('adds hud-panel--dev class when variant="dev"', () => {
    const { container } = render(<HudPanel variant="dev" />);
    expect(container.firstChild).toHaveClass('hud-panel--dev');
  });

  it('does NOT add hud-panel--dev class when variant="default" (default)', () => {
    const { container } = render(<HudPanel />);
    expect(container.firstChild).not.toHaveClass('hud-panel--dev');
  });
});

describe('HudPanel — corner brackets', () => {
  it('renders all four corner bracket spans (tl, tr, bl, br)', () => {
    const { container } = render(<HudPanel />);
    expect(container.querySelector('.hud-corner-bracket.tl')).toBeInTheDocument();
    expect(container.querySelector('.hud-corner-bracket.tr')).toBeInTheDocument();
    expect(container.querySelector('.hud-corner-bracket.bl')).toBeInTheDocument();
    expect(container.querySelector('.hud-corner-bracket.br')).toBeInTheDocument();
  });

  it('corner brackets container has aria-hidden', () => {
    const { container } = render(<HudPanel />);
    const brackets = container.querySelector('.hud-corner-brackets');
    expect(brackets).toHaveAttribute('aria-hidden');
  });
});

describe('HudPanel — light traces', () => {
  it('renders exactly 4 light trace strips', () => {
    const { container } = render(<HudPanel />);
    const traces = container.querySelectorAll('.hud-trace');
    expect(traces).toHaveLength(4);
  });

  it('light trace container has aria-hidden', () => {
    const { container } = render(<HudPanel />);
    const traceWrapper = container.querySelector('.hud-light-trace');
    expect(traceWrapper).toHaveAttribute('aria-hidden');
  });
});

describe('HudPanel — bloom overlay', () => {
  it('renders the bloom overlay element', () => {
    const { container } = render(<HudPanel />);
    expect(container.querySelector('.hud-bloom')).toBeInTheDocument();
  });

  it('bloom overlay has aria-hidden', () => {
    const { container } = render(<HudPanel />);
    expect(container.querySelector('.hud-bloom')).toHaveAttribute('aria-hidden');
  });
});

describe('HudPanel — className and style props', () => {
  it('applies custom className to root element', () => {
    const { container } = render(<HudPanel className="extra-class" />);
    expect(container.firstChild).toHaveClass('extra-class');
  });

  it('applies custom style to root element', () => {
    const { container } = render(<HudPanel style={{ width: 42 }} />);
    expect((container.firstChild as HTMLElement).style.width).toBe('42px');
  });
});
