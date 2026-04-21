/**
 * AudioMuteToggle — Vitest + RTL tests.
 *
 * Tests cover:
 *   - Renders with isMuted=false — shows unmuted icon (speaker on)
 *   - Renders with isMuted=true — shows muted icon + correct aria-label
 *   - aria-pressed reflects mute state
 *   - Click calls onToggle exactly once
 *   - No extra calls on re-render without interaction
 */

import { render, screen } from '@testing-library/react';
import { fireEvent } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AudioMuteToggle } from '../AudioMuteToggle';

afterEach(() => {
  vi.clearAllMocks();
});

describe('AudioMuteToggle — isMuted=false (unmuted state)', () => {
  it('renders the unmuted aria-label', () => {
    render(<AudioMuteToggle isMuted={false} onToggle={vi.fn()} />);
    expect(screen.getByRole('button', { name: /mute sound effects/i })).toBeInTheDocument();
  });

  it('aria-pressed is false when not muted', () => {
    render(<AudioMuteToggle isMuted={false} onToggle={vi.fn()} />);
    const btn = screen.getByRole('button');
    expect(btn).toHaveAttribute('aria-pressed', 'false');
  });

  it('renders polygon SVG path (speaker icon) when unmuted', () => {
    const { container } = render(<AudioMuteToggle isMuted={false} onToggle={vi.fn()} />);
    // The unmuted speaker has a <path> with the arc (d contains "19.07")
    const pathEl = container.querySelector('path[d*="19.07"]');
    expect(pathEl).toBeInTheDocument();
  });
});

describe('AudioMuteToggle — isMuted=true (muted state)', () => {
  it('renders the unmute aria-label', () => {
    render(<AudioMuteToggle isMuted={true} onToggle={vi.fn()} />);
    expect(screen.getByRole('button', { name: /unmute sound effects/i })).toBeInTheDocument();
  });

  it('aria-pressed is true when muted', () => {
    render(<AudioMuteToggle isMuted={true} onToggle={vi.fn()} />);
    const btn = screen.getByRole('button');
    expect(btn).toHaveAttribute('aria-pressed', 'true');
  });

  it('renders line SVG elements (speaker-off X lines) when muted', () => {
    const { container } = render(<AudioMuteToggle isMuted={true} onToggle={vi.fn()} />);
    // The muted speaker has two <line> elements forming the X cross
    const lines = container.querySelectorAll('line');
    expect(lines.length).toBeGreaterThanOrEqual(2);
  });
});

describe('AudioMuteToggle — interaction', () => {
  it('click calls onToggle exactly once', () => {
    const onToggle = vi.fn();
    render(<AudioMuteToggle isMuted={false} onToggle={onToggle} />);
    fireEvent.click(screen.getByRole('button'));
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it('clicking twice calls onToggle twice', () => {
    const onToggle = vi.fn();
    render(<AudioMuteToggle isMuted={false} onToggle={onToggle} />);
    const btn = screen.getByRole('button');
    fireEvent.click(btn);
    fireEvent.click(btn);
    expect(onToggle).toHaveBeenCalledTimes(2);
  });

  it('no extra onToggle calls on re-render without interaction', () => {
    const onToggle = vi.fn();
    const { rerender } = render(<AudioMuteToggle isMuted={false} onToggle={onToggle} />);
    rerender(<AudioMuteToggle isMuted={true} onToggle={onToggle} />);
    expect(onToggle).not.toHaveBeenCalled();
  });
});

describe('AudioMuteToggle — className prop', () => {
  it('applies custom className to the button', () => {
    render(<AudioMuteToggle isMuted={false} onToggle={vi.fn()} className="my-class" />);
    expect(screen.getByRole('button')).toHaveClass('my-class');
  });
});
