import { type ReactElement, type ReactNode } from 'react';
import { Mic } from 'lucide-react';
import './PushToTalkButton.css';

export interface PushToTalkButtonProps {
    active?: boolean;
    onClick?: () => void;
    ariaLabel?: string;
    className?: string;
    children?: ReactNode;
}

export function PushToTalkButton({
    active = false,
    onClick,
    ariaLabel = 'Push to talk',
    className,
    children,
}: PushToTalkButtonProps): ReactElement {
    const classes = ['lib-ptt', active && 'active', className].filter(Boolean).join(' ');

    return (
        <button
            type="button"
            className={classes}
            onClick={onClick}
            aria-label={ariaLabel}
            aria-pressed={active}
        >
            <div className="lib-ptt__rim" aria-hidden="true" />
            {children ?? <Mic size={24} strokeWidth={1.8} aria-hidden="true" />}
        </button>
    );
}

export default PushToTalkButton;
