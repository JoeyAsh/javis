/**
 * Mock WS client factory for feature-level unit tests.
 *
 * ## How to use
 *
 * Call `installMockWsClient()` at module top-level in your test file.
 * Vitest hoists `vi.mock(...)` calls to the top of the transformed module,
 * so the mock factory must not close over local variables.
 * This module works around that limitation by keeping the registry at module
 * scope in a separate shared-state module (`__mockWsRegistry__`), which is
 * always the same reference regardless of import order.
 *
 * ```ts
 * import { installMockWsClient } from '@test/mockWsClient';
 *
 * const ws = installMockWsClient(); // must be at module top-level
 *
 * beforeEach(() => ws.reset());
 *
 * it('handles mail_state', () => {
 *     renderWithProviders(<MailPanel />, { reducers: { mail: mailReducer } });
 *     act(() => ws.emit('mail_state', { messages: [], unread_count: 0 }));
 *     // assert...
 * });
 * ```
 */
import { vi } from 'vitest';
import type { WsMessageHandler } from '@core/websocket/wsClient';

// Module-scope registry — persists across all test files that share this module.
// `installMockWsClient` returns a handle to drive and reset it.
const _registry = new Map<string, Set<WsMessageHandler>>();

export interface MockWsClient {
    /**
     * Invoke every registered subscriber for `type` with a synthetic envelope
     * `{ type, payload }`.
     */
    emit<T>(type: string, payload: T): void;
    /** Return the current subscriber count for `type`. */
    subscribers(type: string): number;
    /** Clear all subscriber registries. Call in beforeEach. */
    reset(): void;
}

/**
 * Replaces the `@core/websocket/wsClient` module with a lightweight fake and
 * returns a control handle for tests to drive messages and inspect state.
 *
 * Must be called at module top-level so that `vi.mock` is hoisted before any
 * component imports.
 */
export function installMockWsClient(): MockWsClient {
    vi.mock('@core/websocket/wsClient', () => {
        // The factory closes over the module-scope `_registry` — this is safe
        // because the import `@test/mockWsClient` is evaluated before the
        // mocked module's subscribers fire.
        const fakeClient = {
            connect: vi.fn(),
            disconnect: vi.fn(),
            send: vi.fn(),
            sendBinary: vi.fn(),
            getState: vi.fn(() => 'closed' as const),
            onStateChange: vi.fn(() => () => undefined),
            subscribe: vi.fn(<T>(type: string, handler: WsMessageHandler<T>): (() => void) => {
                if (!_registry.has(type)) {
                    _registry.set(type, new Set());
                }
                const castHandler = handler as WsMessageHandler;
                // Non-null: we just ensured the key exists above.
                const handlers = _registry.get(type);
                if (handlers) handlers.add(castHandler);
                return () => {
                    _registry.get(type)?.delete(castHandler);
                };
            }),
        };
        return { wsClient: fakeClient };
    });

    return {
        emit<T>(type: string, payload: T): void {
            const handlers = _registry.get(type);
            if (!handlers) return;
            const envelope = { type, payload } as unknown as T;
            handlers.forEach((h) => h(envelope));
        },
        subscribers(type: string): number {
            return _registry.get(type)?.size ?? 0;
        },
        reset(): void {
            _registry.clear();
        },
    };
}
