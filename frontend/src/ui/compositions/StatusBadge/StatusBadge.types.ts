export type StatusBadgeState = 'online' | 'offline' | 'warn';

export interface StatusBadgeProps {
    label?: string;
    state?: StatusBadgeState;
    pulse?: boolean;
    className?: string;
}
