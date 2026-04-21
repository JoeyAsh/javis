import { type ReactElement, type ReactNode } from 'react';
import { Mic } from 'lucide-react';
import { useClickSfx, useHoverSfx } from '../audio/hooks';
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
    const hoverSfx = useHoverSfx('button');
    const clickSfx = useClickSfx(onClick);

    return (
        <button
            type="button"
            className={classes}
            onClick={clickSfx}
            onMouseEnter={hoverSfx}
            aria-label={ariaLabel}
            aria-pressed={active}
            data-sfx-hover="button"
        >
            <div className="lib-ptt__rim" aria-hidden="true" />
            {children ?? <Mic size={24} strokeWidth={1.8} aria-hidden="true" />}
        </button>
    );
}

export default PushToTalkButton;
