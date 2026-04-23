import { useEffect, useRef } from 'react';
import { useAppSelector, useAppDispatch } from '@app/hooks';
import { useStreamConversationModeQuery } from '../conversationApi';
import { followUpTicked } from '../conversationSlice';
import { selectFollowUpActive, selectFollowUpSecondsRemaining } from '../conversationSelectors';
import type { UseConversationModeReturn } from './useConversationMode.types';

const TICK_INTERVAL_MS = 200;
const TICK_DELTA_SECONDS = TICK_INTERVAL_MS / 1000;

/**
 * Subscribe to the backend `conversation_mode` WS stream and expose a
 * smooth, locally-ticking countdown so the HUD can drive sub-second
 * animations without waiting for each WS frame.
 */
export function useConversationMode(): UseConversationModeReturn {
    useStreamConversationModeQuery();
    const dispatch = useAppDispatch();
    const active = useAppSelector(selectFollowUpActive);

    // Mirror active in a ref so the interval callback reads current state
    // without creating a new interval on every active toggle.
    const activeRef = useRef(active);
    activeRef.current = active;

    useEffect(() => {
        const id = window.setInterval(() => {
            if (!activeRef.current) return;
            dispatch(followUpTicked(TICK_DELTA_SECONDS));
        }, TICK_INTERVAL_MS);
        return () => {
            window.clearInterval(id);
        };
    }, [dispatch]);

    return {
        active,
        secondsRemaining: useAppSelector(selectFollowUpSecondsRemaining),
    };
}
