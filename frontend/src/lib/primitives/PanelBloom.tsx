import { type ReactElement } from 'react';
import './PanelBloom.css';

export interface PanelBloomProps {
    active?: boolean;
    className?: string;
}

export function PanelBloom({ active = false, className }: PanelBloomProps): ReactElement {
    return (
        <div
            className={['lib-panel-bloom', active && 'active', className].filter(Boolean).join(' ')}
            aria-hidden="true"
        />
    );
}

export default PanelBloom;
