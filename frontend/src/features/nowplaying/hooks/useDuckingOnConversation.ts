/**
 * useDuckingOnConversation
 *
 * Subscribes to `conversation_state` WS messages and applies unified audio
 * ducking via the AudioEngine orchestrator.
 *
 * - `listening` / `active_dialogue` / `speaking` → immediate duck.
 * - `idle` → restore after TAIL_SILENCE_MS delay (cancelled if state
 *   changes again before the delay elapses).
 *
 * Also registers the Spotify SDK player handle as an ExternalDuckable so
 * the engine can forward duck/restore calls to it. Registration is driven
 * by the playerHandleRegistry subscription so there is no race between
 * sdkIsReady and the registry being populated.
 */

import { useEffect, useRef } from 'react';
import { wsClient } from '@core/websocket/wsClient';
import { getAudioEngine } from '@core/audio/audioEngine';
import { DUCKING_FACTORS, DUCKING_RAMP_MS, TAIL_SILENCE_MS } from '../duckingConstants';
import type { NarrationEngineState } from '../../activity/types';
import type { ConversationStateMessage } from './useDuckingOnConversation.types';
import { playerHandleRegistry } from '../spotifyPlayerHandleRegistry';
import type { SpotifyPlayerHandle } from '../spotifySdk';

/** States that should immediately trigger ducking. */
const ACTIVE_STATES: ReadonlySet<NarrationEngineState> = new Set([
    'listening',
    'active_dialogue',
    'speaking',
]);

export function useDuckingOnConversation(): void {
    const tailTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // ── Register / unregister Spotify SDK as an ExternalDuckable ─────────────
    // Driven by registry subscription so we react to the handle becoming
    // available rather than relying on sdkIsReady, which may fire before
    // playerHandleRegistry.set() has been called.
    useEffect(() => {
        const engine = getAudioEngine();
        let unregister: (() => void) | null = null;

        function bindIfReady(handle: SpotifyPlayerHandle | null): void {
            if (unregister !== null) {
                unregister();
                unregister = null;
            }
            if (handle !== null) {
                unregister = engine.registerExternalDuckable({
                    name: 'spotify',
                    duck: (factor, rampMs) => handle.duck(factor, rampMs),
                    restore: (rampMs) => handle.restore(rampMs),
                });
            }
        }

        // Bind immediately if handle is already present, then track changes.
        bindIfReady(playerHandleRegistry.get());
        const unsubscribeRegistry = playerHandleRegistry.subscribe(bindIfReady);

        return () => {
            unsubscribeRegistry();
            if (unregister !== null) {
                unregister();
            }
        };
    }, []); // run once — registry-driven binding handles all later updates

    // ── Subscribe to conversation_state WS messages ───────────────────────────
    useEffect(() => {
        const engine = getAudioEngine();

        function clearTailTimer(): void {
            if (tailTimerRef.current !== null) {
                clearTimeout(tailTimerRef.current);
                tailTimerRef.current = null;
            }
        }

        const unsubscribe = wsClient.subscribe<ConversationStateMessage>(
            'conversation_state',
            (msg) => {
                const state = msg.payload.state;
                clearTailTimer();

                if (ACTIVE_STATES.has(state)) {
                    engine.setDuckingState('duck', DUCKING_FACTORS, DUCKING_RAMP_MS.down);
                } else if (state === 'idle') {
                    // Defer restore by TAIL_SILENCE_MS — cancel if state changes
                    // again before the delay elapses.
                    tailTimerRef.current = setTimeout(() => {
                        tailTimerRef.current = null;
                        engine.setDuckingState('restore', DUCKING_FACTORS, DUCKING_RAMP_MS.up);
                    }, TAIL_SILENCE_MS);
                }
                // else: unknown future state — leave ducking unchanged.
            },
        );

        return () => {
            clearTailTimer();
            unsubscribe();
        };
    }, []);
}
