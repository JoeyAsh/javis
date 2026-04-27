/**
 * LedgerFilterRow — kind multi-select chips + time-range toggle.
 */
import type { ReactElement } from 'react';
import type { LedgerFilterRowProps } from './LedgerInspector.types';
import type { LedgerKind } from '../../types';
import { ALL_KINDS } from './constants';
import { todayStartMs } from './utils';

export function LedgerFilterRow({
    kindFilter,
    sinceMs,
    onKindsChange,
    onSinceChange,
}: LedgerFilterRowProps): ReactElement {
    function toggleKind(kind: LedgerKind): void {
        if (kindFilter.includes(kind)) {
            onKindsChange(kindFilter.filter((k) => k !== kind));
        } else {
            onKindsChange([...kindFilter, kind]);
        }
    }

    function setTimeRange(label: 'all' | '1h' | 'today'): void {
        if (label === 'all') {
            onSinceChange(null);
        } else if (label === '1h') {
            onSinceChange(Date.now() - 60 * 60 * 1000);
        } else {
            onSinceChange(todayStartMs());
        }
    }

    const todayMs = todayStartMs();
    const activeTimeLabel: 'all' | '1h' | 'today' = (() => {
        if (sinceMs === null) return 'all';
        if (sinceMs <= todayMs + 1000 && sinceMs >= todayMs - 1000) return 'today';
        return '1h';
    })();

    return (
        <div className="flex flex-col gap-1 px-3 py-1.5 border-b border-slate-700/50">
            {/* Time range toggle */}
            <div className="flex items-center gap-1">
                <span className="text-[8px] text-slate-500 uppercase tracking-widest mr-1">Range</span>
                {(['all', '1h', 'today'] as const).map((label) => (
                    <button
                        key={label}
                        type="button"
                        onClick={() => setTimeRange(label)}
                        className={`text-[8px] font-mono px-1.5 py-0.5 rounded-sm border transition-colors ${
                            activeTimeLabel === label
                                ? 'bg-cyan-900/50 text-cyan-300 border-cyan-700/60'
                                : 'bg-slate-800/40 text-slate-500 border-slate-700/40 hover:text-slate-300'
                        }`}
                    >
                        {label}
                    </button>
                ))}
            </div>

            {/* Kind chips */}
            <div className="flex flex-wrap gap-0.5">
                {ALL_KINDS.map((kind) => {
                    const active = kindFilter.includes(kind);
                    return (
                        <button
                            key={kind}
                            type="button"
                            onClick={() => toggleKind(kind)}
                            className={`text-[8px] font-mono px-1.5 py-0.5 rounded-sm border transition-colors ${
                                active
                                    ? 'bg-slate-600/60 text-slate-200 border-slate-500/60'
                                    : 'bg-slate-800/40 text-slate-500 border-slate-700/40 hover:text-slate-300'
                            }`}
                        >
                            {kind}
                        </button>
                    );
                })}
                {kindFilter.length > 0 && (
                    <button
                        type="button"
                        onClick={() => onKindsChange([])}
                        className="text-[8px] font-mono px-1.5 py-0.5 rounded-sm border bg-slate-800/40 text-slate-500 border-slate-700/40 hover:text-slate-300"
                    >
                        clear
                    </button>
                )}
            </div>
        </div>
    );
}

export default LedgerFilterRow;
