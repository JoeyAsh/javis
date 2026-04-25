import type { PanelMode } from '@common/types';
import type { DevToolkitMock } from '../../types';
import type { GitHubStatePayload } from '@core/websocket/types';

export interface DevPanelProps {
    data?: DevToolkitMock;
    mode?: PanelMode;
}

export interface DevCompactProps {
    data: DevToolkitMock;
    liveData: GitHubStatePayload | null;
}

export interface DevExpandedProps {
    data: DevToolkitMock;
    liveData: GitHubStatePayload | null;
}
