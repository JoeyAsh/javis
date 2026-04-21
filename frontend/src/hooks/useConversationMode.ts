import { useEffect, useRef, useState } from 'react';
import { subscribeConversationModeStream } from './useWebSocket';

/**
 * Local view of the backend conversation_mode state.
 *
 * `active` flips true when the backend arms a follow-up window and false
 * when it expires or is closed by a sleep phrase. `secondsRemaining`
 * ticks down locally on a 200 ms interval so the orb countdown ring
 * animates smoothly even between sparse backend broadcasts.
 */
export interface ConversationModeState {
    active: boolean;
    secondsRemaining: number;
}

const TICK_INTERVAL_MS = 200;
const TICK_DELTA_SECONDS = TICK_INTERVAL_MS / 1000;

/**
 * Subscribe to the backend `conversation_mode` WS stream and expose a
 * smooth, locally-ticking countdown so the HUD can drive sub-second
 * animations without waiting for each WS frame.
 */
export function useConversationMode(): ConversationModeState {
    const [state, setState] = useState<ConversationModeState>({
        active: false,
        secondsRemaining: 0,
    });

    // Mirror the latest known state in a ref so the interval callback can
    // read the current seconds without triggering a re-render per tick.
    const stateRef = useRef<ConversationModeState>(state);
    stateRef.current = state;

    useEffect(() => {
        const unsubscribe = subscribeConversationModeStream((payload) => {
            setState({
                active: payload.active,
                secondsRemaining: Math.max(0, payload.seconds_remaining),
            });
        });
        return unsubscribe;
    }, []);

    useEffect(() => {
        const id = window.setInterval(() => {
            const current = stateRef.current;
            if (!current.active) return;
            const next = Math.max(0, current.secondsRemaining - TICK_DELTA_SECONDS);
            setState((prev) =>
                prev.active && prev.secondsRemaining !== next
                    ? { ...prev, secondsRemaining: next }
                    : prev,
            );
        }, TICK_INTERVAL_MS);
        return () => {
            window.clearInterval(id);
        };
    }, []);

    return state;
}
