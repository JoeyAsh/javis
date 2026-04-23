import { type ReactElement } from 'react';
import type { ReactorProps } from './Reactor.types';
import './Reactor.css';

export function Reactor({ className }: ReactorProps): ReactElement {
    return (
        <div className={['lib-reactor', className].filter(Boolean).join(' ')} aria-hidden="true" />
    );
}

export default Reactor;
