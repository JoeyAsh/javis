/**
 * Dock — bottom-center HUD control bar.
 *
 * Composes:
 *   - Left 12-bar audio meter
 *   - 72 px circular push-to-talk button
 *   - Right 12-bar audio meter (mirrored)
 *   - State label + "J A R V I S" brand text
 *
 * PTT audio capture is delegated to `usePushToTalk`; this component owns
 * only the visual presentation.  The legacy `<PushToTalkButton>` component
 * remains in the tree when `enabled` is true but renders null — its keyboard
 * handler is preserved for backwards compatibility.  If pushToTalk is
 * disabled, only the visual dock is shown without the hold-to-record logic.
 */

import type { ReactElement } from 'react';
import React, { useCallback, useEffect } from 'react';
import { usePushToTalk } from '@features/conversation';
import type { AppOrbState } from '../types';
import './Dock.css';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface DockProps {
    /** Current effective orb state — drives meter animation and label. */
    orbState: AppOrbState;
    /** When false the PTT button still renders but audio capture is disabled. */
    pttEnabled: boolean;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const LABEL_FOR_STATE: Record<AppOrbState, string> = {
    idle: 'READY',
    listening: 'listening...',
    thinking: 'thinking...',
    speaking: 'speaking...',
    follow_up: 'follow-up...',
    working: 'working...',
};

const METER_BARS = Array.from({ length: 12 }, (_, i) => i);

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function Dock({ orbState, pttEnabled }: DockProps): ReactElement {
    const { pttState, handlePressStart, handlePressEnd } = usePushToTalk({ enabled: pttEnabled });

    const isActive = orbState !== 'idle';
    const isHolding = pttState === 'holding';

    // Space bar → hold PTT while pressed
    useEffect(() => {
        if (!pttEnabled) return;

        let held = false;

        const onKeyDown = (e: KeyboardEvent): void => {
            if (e.code === 'Space' && !e.ctrlKey && !e.altKey && !e.metaKey && !held) {
                // Avoid triggering when focus is on an interactive element
                const target = e.target as Element;
                const tag = target.tagName.toLowerCase();
                if (tag === 'input' || tag === 'textarea' || tag === 'button' || tag === 'select')
                    return;
                e.preventDefault();
                held = true;
                handlePressStart();
            }
        };

        const onKeyUp = (e: KeyboardEvent): void => {
            if (e.code === 'Space' && held) {
                held = false;
                handlePressEnd();
            }
        };

        window.addEventListener('keydown', onKeyDown);
        window.addEventListener('keyup', onKeyUp);
        return () => {
            window.removeEventListener('keydown', onKeyDown);
            window.removeEventListener('keyup', onKeyUp);
        };
    }, [pttEnabled, handlePressStart, handlePressEnd]);

    const handlePTT = useCallback(() => {
        // Click handler: toggle holding state (touch/click without hold semantics)
        if (isHolding) {
            handlePressEnd();
        } else {
            handlePressStart();
        }
    }, [isHolding, handlePressStart, handlePressEnd]);

    const meterBarStyle = (idle: boolean): React.CSSProperties => ({
        opacity: idle ? 0.2 : 1,
        animationPlayState: idle ? 'paused' : 'running',
        height: idle ? 3 : undefined,
    });

    return (
        <div className="dock">
            {/* Meter + PTT + Meter row */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
                {/* Left meter */}
                <div className="meter" aria-hidden>
                    {METER_BARS.map((i) => (
                        <i key={i} style={meterBarStyle(!isActive)} />
                    ))}
                </div>

                {/* PTT button */}
                <button
                    type="button"
                    className={`ptt${isActive || isHolding ? ' active' : ''}`}
                    onMouseDown={pttEnabled ? handlePressStart : undefined}
                    onMouseUp={pttEnabled ? handlePressEnd : undefined}
                    onMouseLeave={pttEnabled ? handlePressEnd : undefined}
                    onTouchStart={
                        pttEnabled
                            ? (e) => {
                                  e.preventDefault();
                                  handlePressStart();
                              }
                            : undefined
                    }
                    onTouchEnd={
                        pttEnabled
                            ? (e) => {
                                  e.preventDefault();
                                  handlePressEnd();
                              }
                            : undefined
                    }
                    onClick={!pttEnabled ? undefined : handlePTT}
                    aria-label={isHolding ? 'Recording — release to stop' : 'Push to talk'}
                    aria-pressed={isHolding}
                    title="Push to talk"
                >
                    <div className="rim" aria-hidden />
                    <svg
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.8"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        aria-hidden
                    >
                        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                        <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                        <line x1="12" y1="19" x2="12" y2="23" />
                        <line x1="8" y1="23" x2="16" y2="23" />
                    </svg>
                </button>

                {/* Right meter (mirrored) */}
                <div className="meter" style={{ transform: 'scaleX(-1)' }} aria-hidden>
                    {METER_BARS.map((i) => (
                        <i key={i} style={meterBarStyle(!isActive)} />
                    ))}
                </div>
            </div>

            {/* Status row */}
            <div className="dock-status">
                <span className={`state${isActive ? ' on' : ''}`}>{LABEL_FOR_STATE[orbState]}</span>
                <span className="mk">J A R V I S</span>
            </div>
        </div>
    );
}

export default Dock;
