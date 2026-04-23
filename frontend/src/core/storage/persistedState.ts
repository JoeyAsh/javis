/**
 * persistedState — thin localStorage wrapper with safe JSON parse/serialize
 * and optional per-key debounce for save operations.
 *
 * Used by settings and window-layout persistence. No external dependencies.
 */

const debounceTimers = new Map<string, ReturnType<typeof setTimeout>>();

/**
 * Load and JSON-parse a value from localStorage.
 * Returns `fallback` if the key is absent, if JSON parsing fails, or if
 * localStorage is unavailable (e.g. private browsing in some browsers).
 */
export function loadJson<T>(key: string, fallback: T): T {
    try {
        const raw = localStorage.getItem(key);
        if (raw === null) return fallback;
        return JSON.parse(raw) as T;
    } catch {
        return fallback;
    }
}

/**
 * Serialize `value` as JSON and write it to localStorage.
 * When `debounceMs` is provided, the write is deferred — rapid calls with
 * the same key cancel the previous pending write. Pass `0` to write immediately.
 *
 * Silently swallows quota / security errors.
 */
export function saveJson<T>(key: string, value: T, debounceMs = 0): void {
    const write = (): void => {
        try {
            localStorage.setItem(key, JSON.stringify(value));
        } catch {
            // QuotaExceededError or SecurityError — degrade silently.
        }
    };

    if (debounceMs <= 0) {
        write();
        return;
    }

    const existing = debounceTimers.get(key);
    if (existing !== undefined) {
        clearTimeout(existing);
    }

    debounceTimers.set(
        key,
        setTimeout(() => {
            debounceTimers.delete(key);
            write();
        }, debounceMs),
    );
}
