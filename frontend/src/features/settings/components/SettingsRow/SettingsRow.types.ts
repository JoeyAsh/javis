import type { ReactNode } from 'react';

export interface SettingsRowProps {
    /** Left-side label content */
    label: ReactNode;
    /** Right-side control */
    children: ReactNode;
    /** Additional class names applied to the row container */
    className?: string;
}
