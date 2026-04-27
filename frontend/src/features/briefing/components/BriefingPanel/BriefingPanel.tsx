/**
 * BriefingPanel — structured morning briefing HUD card.
 * Subscribes to the `morning_briefing` WS stream and renders payload when fresh.
 */
import type { ReactElement } from 'react';
import { useAppSelector } from '@app/hooks';
import {
    selectBriefingPayload,
    selectBriefingReceivedAt,
    selectBriefingIsFresh,
} from '../../briefingSelectors';
import { useStreamBriefingQuery } from '../../briefingApi';
import { useBriefingAutoClear } from '../../hooks/useBriefingAutoClear';
import { formatLocalTime, formatRelativeTime } from './utils';
import type { BriefingPanelProps } from './BriefingPanel.types';

export function BriefingPanel({ mode: _mode }: BriefingPanelProps): ReactElement {
    // Keep WS subscription alive while panel is mounted.
    useStreamBriefingQuery();

    const payload = useAppSelector(selectBriefingPayload);
    const receivedAt = useAppSelector(selectBriefingReceivedAt);
    const isFresh = useAppSelector(selectBriefingIsFresh);

    // Auto-clear 4 h after receivedAt.
    useBriefingAutoClear(receivedAt);

    if (payload === null || !isFresh) {
        const emptyLabel =
            payload === null || payload.language === 'de'
                ? 'Kein aktuelles Briefing.'
                : 'No current briefing.';
        return (
            <div className="flex items-center justify-center px-4 py-6 text-xs text-white/30">
                {emptyLabel}
            </div>
        );
    }

    const { weather, events, commute, mails, headlines, generatedAt, language } = payload;

    const sectionLabel = language === 'de' ? 'Tages-Briefing' : 'Daily Briefing';
    const relativeTime = formatRelativeTime(generatedAt, language);

    return (
        <div className="flex flex-col gap-3 px-4 py-3 text-sm text-white/80">
            {/* Header */}
            <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-widest text-white/40">
                    {sectionLabel}
                </span>
                <span className="text-xs text-white/30">{relativeTime}</span>
            </div>

            {/* Weather */}
            {weather !== null && (
                <div className="flex items-center gap-2 border-t border-white/10 pt-2">
                    <span className="text-white/50 text-xs uppercase tracking-wide w-16 shrink-0">
                        {language === 'de' ? 'Wetter' : 'Weather'}
                    </span>
                    <span className="text-white/80 text-xs">
                        {weather.condition} · {weather.currentTemp}°
                        {' '}({weather.low}° / {weather.high}°)
                    </span>
                </div>
            )}

            {/* Events */}
            {events.length > 0 && (
                <div className="flex flex-col gap-1 border-t border-white/10 pt-2">
                    <span className="text-white/50 text-xs uppercase tracking-wide mb-1">
                        {language === 'de' ? 'Termine' : 'Events'}
                    </span>
                    {events.slice(0, 2).map((evt) => (
                        <div key={`${evt.start}-${evt.title}`} className="flex items-center gap-2">
                            <span className="text-white/40 text-xs tabular-nums w-10 shrink-0">
                                {formatLocalTime(evt.start)}
                            </span>
                            <span className="text-white/80 text-xs truncate">{evt.title}</span>
                        </div>
                    ))}
                </div>
            )}

            {/* Commute */}
            {commute !== null && commute !== undefined && commute.summary !== undefined && (
                <div className="flex items-center gap-2 border-t border-white/10 pt-2">
                    <span className="text-white/50 text-xs uppercase tracking-wide w-16 shrink-0">
                        {language === 'de' ? 'Weg' : 'Commute'}
                    </span>
                    <span className="text-white/80 text-xs">{commute.summary}</span>
                </div>
            )}

            {/* Mails */}
            {mails.length > 0 && (
                <div className="flex flex-col gap-1 border-t border-white/10 pt-2">
                    <span className="text-white/50 text-xs uppercase tracking-wide mb-1">
                        {language === 'de' ? 'Mails' : 'Mail'}
                    </span>
                    {mails.slice(0, 3).map((mail) => (
                        <div key={`${mail.receivedAt}-${mail.sender}`} className="flex items-center gap-1 min-w-0">
                            <span className="text-white/60 text-xs shrink-0 max-w-[40%] truncate">
                                {mail.sender}
                            </span>
                            <span className="text-white/30 text-xs">—</span>
                            <span className="text-white/80 text-xs truncate">{mail.subject}</span>
                        </div>
                    ))}
                </div>
            )}

            {/* Headlines */}
            {headlines.length > 0 && (
                <div className="flex flex-col gap-1 border-t border-white/10 pt-2">
                    <span className="text-white/50 text-xs uppercase tracking-wide mb-1">
                        {language === 'de' ? 'Schlagzeilen' : 'Headlines'}
                    </span>
                    {headlines.slice(0, 3).map((hl) => (
                        <div key={`${hl.publishedAt ?? ''}-${hl.title}`} className="text-xs truncate">
                            {hl.url !== null ? (
                                <a
                                    href={hl.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-white/70 hover:text-white/90 underline decoration-white/20"
                                >
                                    {hl.title}
                                </a>
                            ) : (
                                <span className="text-white/70">{hl.title}</span>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

export default BriefingPanel;
