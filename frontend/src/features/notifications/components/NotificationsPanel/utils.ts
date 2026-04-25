import type { NotificationSeverity } from '../../types';

export function severityDotStyle(sev: NotificationSeverity): string {
    switch (sev) {
        case 'urgent':
            return 'var(--error, #e05c5c)';
        case 'warning':
            return 'var(--warning, #e0a85c)';
        case 'info':
            return 'var(--accent-bright)';
    }
}

export function severityTitleStyle(sev: NotificationSeverity): string {
    switch (sev) {
        case 'urgent':
            return 'var(--error, #e05c5c)';
        case 'warning':
            return 'var(--warning, #e0a85c)';
        case 'info':
            return 'var(--accent-bright)';
    }
}
