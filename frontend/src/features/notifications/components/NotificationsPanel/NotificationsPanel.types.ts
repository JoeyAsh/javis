import type { HudNotification } from '../../types';
import type { PanelMode } from '../../../../types';

export interface NotificationsPanelProps {
    /** Optional override — short-circuits the live subscription (for tests). */
    notifications?: HudNotification[];
    paused?: boolean;
    mode?: PanelMode;
}
