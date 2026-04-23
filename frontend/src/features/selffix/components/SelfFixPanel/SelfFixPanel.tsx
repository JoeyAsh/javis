import type { ReactElement } from 'react';
import { useSelfFix } from '../../hooks/useSelfFix';
import { SelfFixEntry } from '../SelfFixEntry';
import type { SelfFixPanelProps, SelfFixCompactInnerProps, SelfFixExpandedInnerProps } from './SelfFixPanel.types';
import styles from './SelfFixPanel.module.css';

// ── Compact view ─────────────────────────────────────────────────────────────

function SelfFixCompact({ entries }: SelfFixCompactInnerProps): ReactElement {
    const active = entries.find((e) => e.status === 'in_progress');

    if (active === undefined) {
        return (
            <div className={`window-compact-row ${styles.compact}`}>
                <span className={styles.compactIdle}>Keine Fixes aktiv</span>
            </div>
        );
    }

    return (
        <div className={`window-compact-row ${styles.compact}`}>
            <span className="pulse-dot" aria-hidden />
            <span className={styles.compactStatus}>Fix läuft</span>
            <span className={styles.compactSummary} title={active.summary}>
                {active.summary}
            </span>
        </div>
    );
}

// ── Expanded view ─────────────────────────────────────────────────────────────

function SelfFixExpanded({ entries }: SelfFixExpandedInnerProps): ReactElement {
    return (
        <div className={styles.expanded}>
            {entries.map((e) => (
                <SelfFixEntry key={e.id} entry={e} />
            ))}
        </div>
    );
}

// ── Public component ──────────────────────────────────────────────────────────

export function SelfFixPanel({ entries, mode = 'expanded' }: SelfFixPanelProps): ReactElement {
    const { entries: hookEntries } = useSelfFix();
    const effectiveEntries = entries ?? hookEntries;

    return mode === 'compact' ? (
        <SelfFixCompact entries={effectiveEntries} />
    ) : (
        <SelfFixExpanded entries={effectiveEntries} />
    );
}

export default SelfFixPanel;
