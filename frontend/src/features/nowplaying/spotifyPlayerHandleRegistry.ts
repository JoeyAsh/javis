/**
 * Lightweight module-level registry that holds the current SpotifyPlayerHandle.
 *
 * useSpotifyPlayer sets the handle once the SDK is ready and clears it on
 * cleanup. useDuckingOnConversation subscribes to changes so it can register
 * the Spotify SDK as an ExternalDuckable with the AudioEngine as soon as the
 * handle becomes available — avoiding the race where sdkIsReady fires before
 * the registry is populated.
 *
 * This avoids prop-drilling or React Context for a single non-reactive
 * imperative reference.
 */

import type { SpotifyPlayerHandle } from './spotifySdk';

type Listener = (handle: SpotifyPlayerHandle | null) => void;

let _handle: SpotifyPlayerHandle | null = null;
const _listeners = new Set<Listener>();

export const playerHandleRegistry = {
    get(): SpotifyPlayerHandle | null {
        return _handle;
    },
    set(handle: SpotifyPlayerHandle | null): void {
        _handle = handle;
        _listeners.forEach((l) => l(handle));
    },
    subscribe(listener: Listener): () => void {
        _listeners.add(listener);
        return () => {
            _listeners.delete(listener);
        };
    },
} as const;
