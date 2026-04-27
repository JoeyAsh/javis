/**
 * LedgerHeader — voice composer status strip + 24h kind count chips.
 */
import type { ReactElement } from 'react';
import type { LedgerHeaderProps } from './LedgerInspector.types';
import { relativeTime } from './utils';

export function LedgerHeader({ voiceComposerStatus, counts24h }: LedgerHeaderProps): ReactElement {
    const { last_compose_ts, last_salutation } = voiceComposerStatus;

    return (
        <div className="flex flex-col gap-1 px-3 py-2 border-b border-slate-700/50">
            {/* Voice composer status */}
            <div className="flex items-center gap-2 text-[9px]">
                <span className="text-slate-500 uppercase tracking-widest">Voice Composer</span>
                {last_salutation !== null && (
                    <span className="text-slate-300 font-mono">
                        salutation: <span className="text-cyan-300">{last_salutation}</span>
                    </span>
                )}
                {last_compose_ts !== null && (
                    <span className="text-slate-600 ml-auto">
                        {relativeTime(last_compose_ts)}
                    </span>
                )}
            </div>

            {/* 24h count chips */}
            <div className="flex flex-wrap gap-1">
                {Object.entries(counts24h).map(([kind, count]) => (
                    <span
                        key={kind}
                        className="text-[8px] font-mono px-1.5 py-0.5 bg-slate-800/60 text-slate-400 border border-slate-700/40 rounded-sm"
                    >
                        {kind} <span className="text-slate-300">{count}</span>
                    </span>
                ))}
            </div>
        </div>
    );
}

export default LedgerHeader;
