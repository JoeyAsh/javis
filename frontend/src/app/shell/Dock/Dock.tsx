/**
 * Dock — bottom-center dock composed from the ui StatusDock + PTT logic.
 *
 * Wires push-to-talk (keyboard Space + pointer hold) from @features/conversation.
 */

import { type ReactElement, useCallback, useEffect } from 'react';
import { PushToTalkButton, StatusDock } from '@ui';
import { usePushToTalk } from '@features/conversation';
import type { AppOrbState } from '@common/types';
import type { DockProps } from './Dock.types';

function toDisplayState(state: AppOrbState): AppOrbState {
    if (state === 'follow_up') return 'listening';
    return state;
}

export function Dock({ orbState, pttEnabled }: DockProps): ReactElement {
    const { pttState, handlePressStart, handlePressEnd } = usePushToTalk({ enabled: pttEnabled });
    const isHolding = pttState === 'holding';
    const isActive = orbState !== 'idle';

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

export default Dock;
