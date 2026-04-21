import { type ReactElement, type ReactNode } from 'react';
import './Hint.css';

export interface HintKeyProps {
    children: ReactNode;
    className?: string;
}

function HintKey({ children, className }: HintKeyProps): ReactElement {
    return <kbd className={['lib-hint__kbd', className].filter(Boolean).join(' ')}>{children}</kbd>;
}

export interface HintProps {
    children: ReactNode;
    position?: 'fixed-br' | 'inline';
    className?: string;
}

function HintRoot({ children, position = 'fixed-br', className }: HintProps): ReactElement {
    const classes = ['lib-hint', position, className].filter(Boolean).join(' ');
    return <div className={classes}>{children}</div>;
}

export const Hint = Object.assign(HintRoot, { Key: HintKey });

export default Hint;
