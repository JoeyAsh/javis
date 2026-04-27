# Template: `components/<Name>Panel/__tests__/<Name>Panel.test.tsx`

```tsx
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '@test/renderWithProviders';
import { installMockWsClient } from '@test/mockWsClient';
import <name>Reducer, { <name>DataReceived } from '../../../<name>Slice';
import { <Name>Panel } from '../<Name>Panel';

vi.mock('@core/websocket/wsClient', () => import('@test/mockWsClient').then((m) => ({ wsClient: m._mockWsClientImpl })));

describe('<Name>Panel', () => {
    let ws: ReturnType<typeof installMockWsClient>;

    beforeEach(() => {
        ws = installMockWsClient();
    });

    it('renders loading state before first payload', () => {
        renderWithProviders(<<Name>Panel />, { reducers: { <name>: <name>Reducer } });
        expect(screen.getByText(/loading/i)).toBeInTheDocument();
    });

    it('renders data after <msg_type> payload arrives', () => {
        const { store } = renderWithProviders(<<Name>Panel />, { reducers: { <name>: <name>Reducer } });
        store.dispatch(<name>DataReceived({ /* mock payload */ }));
        // expect(...).toBeInTheDocument();
    });
});
```
