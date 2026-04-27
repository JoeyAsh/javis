// Public barrel — consumers import from '@features/activity', not from internal paths.
export { ActivityPanel } from './components/ActivityPanel';
export type { ActivityPanelProps } from './components/ActivityPanel';
export { useActivity } from './hooks/useActivity';
export type { UseActivityReturn } from './hooks/useActivity.types';
export { activityApi, useStreamActivityQuery } from './activityApi';
export { narrationStateReceived, activityPanelReceived } from './activitySlice';
export type { ActivityState } from './activitySlice';
export {
    selectActivityState,
    selectQuietUntil,
    selectActivitySources,
    selectActivityHistory,
    selectActivityHasLiveData,
} from './activitySelectors';
export type {
    NarrationItem,
    NarrationSeverity,
    NarrationEngineState,
    SourceEntry,
    SourceStatus,
    NarrationStatePayload,
    ActivityPanelPayload,
} from './types';
