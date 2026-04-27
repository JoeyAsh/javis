/**
 * Resolves the JARVIS API bearer token from one of three sources, in priority
 * order:
 *
 *  1. `import.meta.env.VITE_JARVIS_TOKEN` — Vite build-time env var (local dev).
 *  2. `localStorage["jarvis_api_token"]`   — operator-written for deployed builds.
 *  3. `""`                                  — fallback; token auth disabled client-side.
 *
 * This is a plain function (not a hook) so it can be called from both RTK
 * Query's `prepareHeaders` and `wsClient.connect`.
 */

export function getApiToken(): string {
    const envToken = import.meta.env.VITE_JARVIS_TOKEN;
    if (typeof envToken === 'string' && envToken.length > 0) {
        return envToken;
    }

    try {
        const stored = localStorage.getItem('jarvis_api_token');
        if (stored !== null && stored.length > 0) {
            return stored;
        }
    } catch (err) {
        console.warn('[tokenStore] localStorage unavailable — token auth disabled client-side.', err);
    }

    return '';
}
