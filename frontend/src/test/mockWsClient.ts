/**
 * Mock WS client factory for feature-level unit tests.
 *
 * ## Usage
 *
 * Add these two lines at the **top** of every test file that needs WS:
 *
 * ```ts
 * import { installMockWsClient } from '@test/mockWsClient';
 *
 * // vi.mock is hoisted by Vitest — keep at module top-level
 * vi.mock('@core/websocket/wsClient', () => ({ wsClient: _mockWsClientImpl }));
 *
 * const ws = installMockWsClient();
 * ```
 *
 * The exported `_mockWsClientImpl` is the singleton fake that Vitest will
 * substitute for the real `wsClient`. `installMockWsClient()` returns a
 * control handle with `emit`, `subscribers`, and `reset`.
 */
import { vi } from 'vitest';
import type { WsMessageHandler } from '@core/websocket/wsClient';

// Module-scope registry — persists across all test files that share this module.
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
 * The fake wsClient implementation that `vi.mock` will expose.
 * Import this in your test file and pass it to the `vi.mock` factory.
 *
 * Vitest hoists `vi.mock(...)` calls to the top of the transformed module,
 * so the factory MUST NOT close over local variables declared after the
 * import block. This object is defined at module scope, so it is always
 * available when the factory runs.
 */
export const _mockWsClientImpl = {
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
        const handlers = _registry.get(type);
        if (handlers) handlers.add(castHandler);
        return () => {
            _registry.get(type)?.delete(castHandler);
        };
    }),
};

/**
 * Returns a control handle to drive mock WS messages and reset state in tests.
 *
 * Call at module top-level after the `vi.mock` call:
 * ```ts
 * vi.mock('@core/websocket/wsClient', () => ({ wsClient: _mockWsClientImpl }));
 * const ws = installMockWsClient();
 * ```
 */
export function installMockWsClient(): MockWsClient {
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
            vi.clearAllMocks();
            // Re-attach subscribe mock after clearAllMocks resets it.
            _mockWsClientImpl.subscribe.mockImplementation(
                <T>(type: string, handler: WsMessageHandler<T>): (() => void) => {
                    if (!_registry.has(type)) {
                        _registry.set(type, new Set());
                    }
                    const castHandler = handler as WsMessageHandler;
                    const handlers = _registry.get(type);
                    if (handlers) handlers.add(castHandler);
                    return () => {
                        _registry.get(type)?.delete(castHandler);
                    };
                },
            );
        },
    };
}
