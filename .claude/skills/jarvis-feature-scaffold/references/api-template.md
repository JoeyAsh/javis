# Template: `<name>Api.ts`

```ts
import { baseApi } from '@core/api/baseApi';
import { wsClient } from '@core/websocket/wsClient';
import type { <Name>Payload } from './types';
import { <name>DataReceived } from './<name>Slice';

export const <name>Api = baseApi.injectEndpoints({
    endpoints: (builder) => ({
        stream<Name>: builder.query<null, void>({
            queryFn: () => ({ data: null }),
            async onCacheEntryAdded(_arg, { cacheDataLoaded, cacheEntryRemoved, dispatch }) {
                await cacheDataLoaded;
                const unsub = wsClient.subscribe<{ type: string; payload: <Name>Payload }>(
                    '<msg_type>',
                    (msg) => dispatch(<name>DataReceived(msg.payload)),
                );
                await cacheEntryRemoved;
                unsub();
            },
        }),
    }),
});

export const { useStream<Name>Query } = <name>Api;
```
