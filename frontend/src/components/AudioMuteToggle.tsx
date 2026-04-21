/**
 * AudioMuteToggle — standalone icon button that toggles SFX mute.
 *
 * Deliberately has no layout assumptions: place it anywhere with `className`.
 * Styling follows the JARVIS design system (JetBrains Mono, hairline border,
 * 2 px radius, CSS-variable colors only).
 */

import type { ReactElement } from 'react';

export interface AudioMuteToggleProps {
  isMuted: boolean;
  onToggle: () => void;
  className?: string;
}

/** Speaker icon (sound on). */
function IconSpeaker(): ReactElement {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      focusable="false"
    >
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
      <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
      <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
    </svg>
  );
}

/** Speaker-off icon (muted). */
function IconSpeakerOff(): ReactElement {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      focusable="false"
    >
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
      <line x1="23" y1="9" x2="17" y2="15" />
      <line x1="17" y1="9" x2="23" y2="15" />
    </svg>
  );
}

export function AudioMuteToggle({
  isMuted,
  onToggle,
  className,
}: AudioMuteToggleProps): ReactElement {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={isMuted ? 'Unmute sound effects' : 'Mute sound effects'}
      aria-pressed={isMuted}
      className={className}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: 28,
        height: 28,
        background: 'rgba(13,13,20,0.6)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--r-1)',
        cursor: 'pointer',
        color: isMuted ? 'var(--text-muted)' : 'var(--accent)',
        fontFamily: 'var(--font)',
        transition: 'color var(--dur-base) var(--ease), border-color var(--dur-base) var(--ease), box-shadow var(--dur-base) var(--ease)',
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLButtonElement).style.boxShadow = 'var(--glow)';
        (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--accent)';
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLButtonElement).style.boxShadow = '';
        (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--border)';
      }}
    >
      {isMuted ? <IconSpeakerOff /> : <IconSpeaker />}
    </button>
  );
}

export default AudioMuteToggle;
