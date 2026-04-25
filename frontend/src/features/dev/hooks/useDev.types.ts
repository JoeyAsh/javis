import type { GitHubStatePayload } from '@core/websocket/types';
import type { DevToolkitMock } from '../types';

export interface UseDevReturn {
    liveData: GitHubStatePayload | null;
    loading: boolean;
    mockData: DevToolkitMock;
}
