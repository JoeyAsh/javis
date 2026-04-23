/**
 * NotificationsView — notifications panel content.
 * Thin wrapper around legacy NotificationsPanel during Phase 3 migration.
 * TODO: Rewrite internals to use lib primitives.
 */
export {
    NotificationsPanel as NotificationsView,
    NotificationsPanel as default,
} from '../components/panels/Notifications/NotificationsPanel';
export type {
    NotificationsPanelProps as NotificationsViewProps,
} from '../components/panels/Notifications/NotificationsPanel';

