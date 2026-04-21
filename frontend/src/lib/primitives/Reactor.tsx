import { type ReactElement } from 'react';
import './Reactor.css';

export interface ReactorProps {
    className?: string;
}

export function Reactor({ className }: ReactorProps): ReactElement {
    return (
        <div className={['lib-reactor', className].filter(Boolean).join(' ')} aria-hidden="true" />
    );
}

export default Reactor;
