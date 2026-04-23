import type { ReactNode } from 'react';

export interface PushToTalkButtonProps {
    active?: boolean;
    onClick?: () => void;
    ariaLabel?: string;
    className?: string;
    children?: ReactNode;
}
