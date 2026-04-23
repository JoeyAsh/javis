import { useCallback, useMemo, useRef, useState, useEffect } from 'react';
import type { ReactElement } from 'react';
import { useLog } from '../../hooks/useLog';
import type { LogLinePayload } from '../../types';
import { LogLine } from '../LogLine';
import { LogFilters } from '../LogFilters';
import { TurnTimingSummary } from '../TurnTimingSummary';
import type { LogPanelProps, StreamViewProps } from './LogPanel.types';
import styles from './LogPanel.module.css';

type TabId = 'stream' | 'timeline';

const VISIBLE_LINES = 100;

// ---------------------------------------------------------------------------
// Stream view
// ---------------------------------------------------------------------------

function StreamView({ lines, onClear }: StreamViewProps): ReactElement {
    const scrollRef = useRef<HTMLDivElement>(null);
    const [hovering, setHovering] = useState(false);

    useEffect(() => {
        if (!hovering && scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [lines, hovering]);

    const visible = useMemo(() => {
        if (lines.length <= VISIBLE_LINES) return lines;
        return lines.slice(lines.length - VISIBLE_LINES);
    }, [lines]);

    return (
        <div className={styles.stream}>
            <LogFilters lineCount={lines.length} paused={hovering} onClear={onClear} />
            <div
                ref={scrollRef}
                className={styles.scroll}
                onMouseEnter={() => setHovering(true)}
                onMouseLeave={() => setHovering(false)}
            >
                {visible.length === 0 ? (
                    <div className={styles.empty}>Waiting for log stream…</div>
                ) : (
                    visible.map((entry: LogLinePayload, idx: number) => (
                        <LogLine
                            key={`${entry.timestamp}-${idx}-${entry.message.slice(0, 16)}`}
                            entry={entry}
                        />
                    ))
                )}
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// LogPanel root
// ---------------------------------------------------------------------------

export function LogPanel({ mode }: LogPanelProps): ReactElement {
    const { lines, turnTimings, clear } = useLog();
    const [activeTab, setActiveTab] = useState<TabId>('stream');

    const handleTabClick = useCallback((tab: TabId) => {
        setActiveTab(tab);
    }, []);

    const tabClass = (tab: TabId): string =>
        `${styles.tab} ${activeTab === tab ? styles.tabActive : styles.tabInactive}`;

    const streamLabel = mode === 'compact' ? 'Log' : 'Log Stream';
    const timelineLabel = mode === 'compact' ? 'Timeline' : 'Turn Timeline';

    return (
        <div className={styles.panel}>
            <div className={styles.tabs}>
                <button
                    type="button"
                    className={tabClass('stream')}
                    onClick={() => handleTabClick('stream')}
                >
                    {streamLabel}
                </button>
                <button
                    type="button"
                    className={tabClass('timeline')}
                    onClick={() => handleTabClick('timeline')}
                >
                    {timelineLabel}
                </button>
            </div>
            <div className={styles.content}>
                {activeTab === 'stream' ? (
                    <StreamView lines={lines} onClear={clear} />
                ) : (
                    <TurnTimingSummary turns={turnTimings} />
                )}
            </div>
        </div>
    );
}

export default LogPanel;
