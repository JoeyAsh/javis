import { type ReactNode, type ReactElement } from 'react';
import './TopBar.css';

export interface TopBarProps {
    left?: ReactNode;
    center?: ReactNode;
    right?: ReactNode;
    className?: string;
}

export function TopBar({ left, center, right, className }: TopBarProps): ReactElement {
    return (
        <div className={['lib-topbar', className].filter(Boolean).join(' ')}>
            {/* Bottom corner brackets (::before and ::after on .lib-topbar handle tl/tr) */}
            <span className="lib-topbar__c-bl" />
            <span className="lib-topbar__c-br" />

            {/* Circumnavigating trace */}
            <span className="lib-topbar__trace">
                <i className="lib-topbar__trace-l" />
                <i className="lib-topbar__trace-r" />
            </span>

            <div className="lib-topbar__left">{left}</div>
            <div className="lib-topbar__center">{center}</div>
            <div className="lib-topbar__right">{right}</div>
        </div>
    );
}

export default TopBar;
