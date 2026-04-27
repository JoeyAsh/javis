/**
 * Unit tests for getApiToken() in tokenStore.ts.
 *
 * Strategy:
 *  - vi.stubEnv controls import.meta.env.VITE_JARVIS_TOKEN.
 *  - jsdom's in-memory localStorage is reset between tests via localStorage.clear().
 *  - The SecurityError path mocks localStorage.getItem to throw.
 *
 * vi.resetModules() + dynamic import ensures each test gets a fresh module
 * evaluation (important because the function reads live globals each call, but
 * re-importing ensures mock state is clean and avoids cross-test pollution).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const VALID_TOKEN = 'a'.repeat(64);

beforeEach(() => {
    localStorage.clear();
    vi.unstubAllEnvs();
    vi.resetModules();
});

afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Helper: import a fresh copy of tokenStore after env stubs are set.
// ---------------------------------------------------------------------------

async function freshGetApiToken(): Promise<() => string> {
    const mod = await import('../tokenStore');
    return mod.getApiToken;
}

describe('getApiToken — VITE_JARVIS_TOKEN env var', () => {
    it('returns the env var value when VITE_JARVIS_TOKEN is set to a non-empty string', async () => {
        /**
         * Primary resolution path: env var is present and truthy.
         */
        vi.stubEnv('VITE_JARVIS_TOKEN', VALID_TOKEN);
        const getApiToken = await freshGetApiToken();
        expect(getApiToken()).toBe(VALID_TOKEN);
    });

    it('falls through to localStorage when VITE_JARVIS_TOKEN is an empty string', async () => {
        /**
         * Empty-string env var must not be treated as set — should fall through.
         */
        vi.stubEnv('VITE_JARVIS_TOKEN', '');
        localStorage.setItem('jarvis_api_token', 'from-localstorage');
        const getApiToken = await freshGetApiToken();
        expect(getApiToken()).toBe('from-localstorage');
    });
});

describe('getApiToken — localStorage fallback', () => {
    it('returns localStorage value when env var is absent and localStorage is set', async () => {
        /**
         * AC 13: falls through to localStorage["jarvis_api_token"] when env var absent.
         */
        // env var deliberately not stubbed (remains undefined).
        localStorage.setItem('jarvis_api_token', VALID_TOKEN);
        const getApiToken = await freshGetApiToken();
        expect(getApiToken()).toBe(VALID_TOKEN);
    });

    it('returns empty string when neither env var nor localStorage is set', async () => {
        /**
         * Final fallback: both sources empty → "".
         */
        const getApiToken = await freshGetApiToken();
        expect(getApiToken()).toBe('');
    });

    it('returns empty string and logs console.warn when localStorage throws SecurityError', async () => {
        /**
         * Edge case: private-browsing / sandboxed iframe where localStorage access is
         * blocked. getApiToken() must not throw — it returns "" and emits a warn.
         */
        const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
        const getItemSpy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
            const err = new DOMException('SecurityError', 'SecurityError');
            throw err;
        });

        const getApiToken = await freshGetApiToken();
        const result = getApiToken();

        expect(result).toBe('');
        expect(warnSpy).toHaveBeenCalledOnce();
        expect(warnSpy.mock.calls[0][0]).toContain('localStorage');

        getItemSpy.mockRestore();
        warnSpy.mockRestore();
    });
});
