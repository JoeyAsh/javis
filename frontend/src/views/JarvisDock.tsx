/**
 * JarvisDock — bottom-center dock composed from lib StatusDock + PTT logic.
 *
 * Wraps the lib StatusDock composition and wires the push-to-talk hook
 * (keyboard Space + pointer hold) from the business-logic layer.
 */

import React, { type ReactElement, useCallback, useEffect } from 'react';
import { PushToTalkButton, StatusDock } from '@ui';
import { usePushToTalk } from '../hooks/usePushToTalk';
import type { AppOrbState } from '@common/types';

// ── Props ────────────────────────────────────────────────────────────────────

export interface JarvisDockProps {
    orbState: AppOrbState;
    wsRef: React.RefObject<WebSocket | null>;
    pttEnabled: boolean;
}

/** Map follow_up → listening for dock display (mic stays open but subtler). */
function toDisplayState(state: AppOrbState): AppOrbState {
    if (state === 'follow_up') return 'listening';
    return state;
}

// ── Component ────────────────────────────────────────────────────────────────

export function JarvisDock({ orbState, wsRef, pttEnabled }: JarvisDockProps): ReactElement {
    const { pttState, handlePressStart, handlePressEnd } = usePushToTalk({ wsRef });
    const isHolding = pttState === 'holding';
    const isActive = orbState !== 'idle';

    // Space bar → hold PTT while pressed
    useEffect(() => {
        if (!pttEnabled) return;

        let held = false;

        const onKeyDown = (e: KeyboardEvent): void => {
            if (e.code === 'Space' && !e.ctrlKey && !e.altKey && !e.metaKey && !held) {
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
        if (isHolding) {
            handlePressEnd();
        } else {
            handlePressStart();
        }
    }, [isHolding, handlePressStart, handlePressEnd]);

    return (
        <StatusDock
            state={toDisplayState(orbState)}
            onPTT={pttEnabled ? handlePTT : undefined}
            ptt={
                <PushToTalkButton
                    active={isActive || isHolding}
                    onClick={pttEnabled ? handlePTT : undefined}
                    ariaLabel={isHolding ? 'Recording — release to stop' : 'Push to talk'}
                />
            }
        />
    );
}

export default JarvisDock;

