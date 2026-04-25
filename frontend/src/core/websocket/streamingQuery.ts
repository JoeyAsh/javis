/**
 * Helper for RTK Query streaming queries backed by the singleton WsClient.
 *
 * Usage:
 *   onCacheEntryAdded: createStreamingQueryHandler<MailStatePayload, MailMessage[]>(
 *       'mail_state',
 *       (_prev, payload) => payload.messages,
 *   ),
 */

import { wsClient } from './wsClient';

type OnCacheEntryAddedApi<TCache> = {
    cacheDataLoaded: Promise<{ data: TCache }>;
    cacheEntryRemoved: Promise<void>;
    updateCachedData: (recipe: (draft: TCache) => void) => void;
};

/**
 * Creates an `onCacheEntryAdded` handler for an RTK Query endpoint that
 * subscribes to WS messages of `messageType` and updates the cache via
 * the provided `reducer`.
 *
 * @param messageType - The `type` field on incoming WS messages to subscribe to.
 * @param reducer     - Transforms (currentCache, incomingPayload) → nextCache.
 */
export function createStreamingQueryHandler<TMessage, TCache>(
    messageType: string,
    reducer: (current: TCache, payload: TMessage) => TCache,
): (arg: unknown, api: OnCacheEntryAddedApi<TCache>) => Promise<void> {
    return async (_arg: unknown, api: OnCacheEntryAddedApi<TCache>): Promise<void> => {
        await api.cacheDataLoaded;

        const unsubscribe = wsClient.subscribe<TMessage>(messageType, (payload) => {
            api.updateCachedData((draft) => {
                // Return the new value; Immer will handle it via produce.
                const next = reducer(draft as TCache, payload);
                // Replace draft content with next value.
                Object.assign(draft as object, next);
            });
        });

        await api.cacheEntryRemoved;
        unsubscribe();
    };
}
