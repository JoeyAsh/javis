import { type ReactElement } from 'react';
import './PanelRails.css';

export interface PanelRailsProps {
    className?: string;
    visible?: boolean;
}

export function PanelRails({ className, visible = false }: PanelRailsProps): ReactElement {
    return (
        <div
            className={['lib-panel-rails', visible && 'visible', className]
                .filter(Boolean)
                .join(' ')}
            aria-hidden="true"
        >
            <span className="lib-panel-rails__rail lib-panel-rails__rail--l" />
            <span className="lib-panel-rails__rail lib-panel-rails__rail--r" />
        </div>
    );
}

export default PanelRails;
