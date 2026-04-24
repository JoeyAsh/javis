import { useEffect, useRef } from 'react';
import type { ReactElement } from 'react';
import { TranscriptEntry } from '../TranscriptEntry';
import { ThinkingDots } from '../ThinkingDots';
import type { TranscriptExpandedProps } from './TranscriptExpanded.types';
import styles from './TranscriptPanel.module.css';

export function TranscriptExpanded({ turns, orbState }: TranscriptExpandedProps): ReactElement {
    const bottomRef = useRef<HTMLDivElement | null>(null);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }, [turns, orbState]);

    return (
        <div className={styles.panel}>
            {turns.map((t) => (
                <TranscriptEntry key={t.id} turn={t} />
            ))}
            {orbState === 'thinking' && <ThinkingDots />}
            <div ref={bottomRef} />
        </div>
    );
}

export default TranscriptExpanded;
