/**
 * Types for useDuckingOnConversation hook.
 */

import type { NarrationEngineState } from '../../activity/types';

/** Shape of the `conversation_state` WS message delivered by the backend. */
export interface ConversationStateMessage {
    type: string;
    payload: {
        state: NarrationEngineState;
        /** ISO 8601 timestamp of when the state was entered. */
        since: string;
    };
}
