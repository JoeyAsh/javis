import { type CSSProperties, type ReactElement } from 'react';
import './LightTrace.css';

export interface LightTraceProps {
    className?: string;
    color?: string;
}

export function LightTrace({ className, color }: LightTraceProps): ReactElement {
    const style = color !== undefined ? ({ '--lt-color': color } as CSSProperties) : undefined;

    return (
        <span
            className={['lib-lighttrace', className].filter(Boolean).join(' ')}
            style={style}
            aria-hidden="true"
        >
            <i className="lib-lighttrace__l" />
            <i className="lib-lighttrace__r" />
        </span>
    );
}

export default LightTrace;
