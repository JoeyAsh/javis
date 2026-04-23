import type { ReactElement } from 'react';
import type { SettingsRowProps } from './SettingsRow.types';

/** SettingsRow — label on left, control on right. */
export function SettingsRow({ label, children, className }: SettingsRowProps): ReactElement {
    return (
        <div className={['flex items-center justify-between gap-3 mb-[14px]', className].filter(Boolean).join(' ')}>
            <span>{label}</span>
            <span>{children}</span>
        </div>
    );
}

export default SettingsRow;
