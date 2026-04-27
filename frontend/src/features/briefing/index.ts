// Public API for the briefing feature.
export { BriefingPanel } from './components/BriefingPanel';
export type { BriefingPanelProps } from './components/BriefingPanel';

export { briefingReceived, briefingCleared } from './briefingSlice';
export { default as briefingReducer } from './briefingSlice';

export { briefingApi, useStreamBriefingQuery } from './briefingApi';

export type {
    BriefingPayload,
    BriefingMail,
    BriefingHeadline,
    BriefingEvent,
    BriefingWeather,
    BriefingCommute,
    BriefingState,
} from './types';
