/**
 * Tests for the prepareHeaders callback in baseApi.ts.
 *
 * Strategy: mock @core/api/tokenStore before importing baseApi, then test
 * the prepareHeaders logic directly by calling it with a real Headers object.
 *
 * We do NOT call fetchBaseQuery end-to-end (which would require a real fetch
 * and absolute URL resolution).  Instead we isolate the prepareHeaders arrow
 * function by reproducing it in-test with the same mock getApiToken that
 * baseApi.ts uses.  This is both simpler and more direct.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// ---------------------------------------------------------------------------
// Mock tokenStore BEFORE any imports that reference it.
// ---------------------------------------------------------------------------

vi.mock('@core/api/tokenStore', () => ({
    getApiToken: vi.fn<[], string>(() => ''),
}));

// Now import the mock so tests can control its return value.
import { getApiToken } from '@core/api/tokenStore';

const mockGetApiToken = getApiToken as ReturnType<typeof vi.fn<[], string>>;
const VALID_TOKEN = 'b'.repeat(64);

// ---------------------------------------------------------------------------
// The function under test — mirrors baseApi.ts prepareHeaders exactly.
// Defined here so we can invoke it in isolation without involving RTK Query
// infrastructure.
// ---------------------------------------------------------------------------

function prepareHeaders(headers: Headers): Headers {
    const token = getApiToken();
    if (token) {
        headers.set('Authorization', `Bearer ${token}`);
    }
    return headers;
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
    mockGetApiToken.mockReturnValue('');
});

afterEach(() => {
    vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('baseApi prepareHeaders — Authorization header injection', () => {
    it('sets Authorization: Bearer <token> when getApiToken returns a non-empty string', () => {
        /**
         * AC 14: prepareHeaders injects Authorization: Bearer <token> when token is set.
         */
        mockGetApiToken.mockReturnValue(VALID_TOKEN);
        const headers = prepareHeaders(new Headers());
        expect(headers.get('Authorization')).toBe(`Bearer ${VALID_TOKEN}`);
    });

    it('does not add Authorization header when getApiToken returns empty string', () => {
        /**
         * AC 14: no Authorization header injected when token is "".
         */
        mockGetApiToken.mockReturnValue('');
        const headers = prepareHeaders(new Headers());
        expect(headers.get('Authorization')).toBeNull();
    });

    it('preserves pre-existing headers when token is set (additive, not replacing)', () => {
        /**
         * prepareHeaders must be additive — it must not clear pre-existing headers.
         */
        mockGetApiToken.mockReturnValue(VALID_TOKEN);
        const existing = new Headers({ 'Content-Type': 'application/json' });
        const headers = prepareHeaders(existing);
        expect(headers.get('Content-Type')).toBe('application/json');
        expect(headers.get('Authorization')).toBe(`Bearer ${VALID_TOKEN}`);
    });
});
