/**
 * Outgoing one-way WS command helpers.
 * Consumers import these instead of calling wsClient.send directly
 * so the wire shape stays in one place.
 */

import { wsClient } from './wsClient';
import type { SpotifyCmdAction } from './types';

export function sendTranscript(text: string, isFinal = true): void {
    wsClient.send({ type: 'transcript', text, isFinal });
}

export function sendCancelTurn(): void {
    wsClient.send({ type: 'cancel_turn' });
}

export function sendSpotifyCmd(action: SpotifyCmdAction, value?: number): void {
    const payload = value !== undefined ? { action, value } : { action };
    wsClient.send({ type: 'spotify_cmd', payload });
}
