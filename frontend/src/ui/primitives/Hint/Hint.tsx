import { type ReactElement } from 'react';
import type { HintKeyProps, HintProps } from './Hint.types';

function HintKey({ children, className }: HintKeyProps): ReactElement {
    return <kbd className={['lib-hint__kbd', className].filter(Boolean).join(' ')}>{children}</kbd>;
}

function HintRoot({ children, position = 'fixed-br', className }: HintProps): ReactElement {
    const classes = ['lib-hint', position, className].filter(Boolean).join(' ');
    return <div className={classes}>{children}</div>;
}

export const Hint = Object.assign(HintRoot, { Key: HintKey });

export default Hint;
