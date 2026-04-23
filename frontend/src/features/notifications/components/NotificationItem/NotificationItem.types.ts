import type { HudNotification } from '../../types';

export interface NotificationItemProps {
    notification: HudNotification;
    onClick?: (id: string) => void;
}
