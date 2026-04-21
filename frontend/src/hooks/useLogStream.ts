/**
 * useLogStream — subscribes to backend ``log_line`` WS messages and
 * maintains a ring buffer of the last N entries.
 *
 * Auto-scroll pausing is signalled via the ``paused`` flag — the consumer
 * manages scroll state; this hook just exposes the buffer.
 */
import { useEffect, useRef, useState } from 'react';
import type { LogLinePayload } from '../types';
import { subscribeLogLineStream } from './useWebSocket';

export interface UseLogStreamReturn {
    /** Ring-buffered log lines, oldest first. Max length = `maxLines`. */
    lines: ReadonlyArray<LogLinePayload>;
    /** Clear the in-memory buffer. */
    clear: () => void;
}

/** Maximum log lines kept in memory. Matches config.yaml default. */
const DEFAULT_MAX_LINES = 500;

/**
 * Subscribe to the backend log stream and maintain a ring buffer.
 *
 * @param maxLines - Maximum entries to keep (default 500).
 */
export function useLogStream(maxLines: number = DEFAULT_MAX_LINES): UseLogStreamReturn {
    const [lines, setLines] = useState<ReadonlyArray<LogLinePayload>>([]);
    // Keep maxLines in a ref so the listener closure always reads the latest value
    // without needing to re-subscribe.
    const maxLinesRef = useRef(maxLines);
    useEffect(() => {
        maxLinesRef.current = maxLines;
    }, [maxLines]);

    useEffect(() => {
        const unsub = subscribeLogLineStream((payload: LogLinePayload) => {
            setLines((prev) => {
                const next = [...prev, payload];
                const max = maxLinesRef.current;
                return next.length > max ? next.slice(next.length - max) : next;
            });
        });
        return unsub;
    }, []);

    const clear = (): void => {
        setLines([]);
    };

    return { lines, clear };
}

export default useLogStream;
