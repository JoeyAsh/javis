import type { ReactElement } from 'react';
import { useClickSfx, useHoverSfx } from '@core/audio';
import type { ToggleRowProps } from './Tweaks.types';

export function ToggleRow({ label, value, onToggle }: ToggleRowProps): ReactElement {
    const hoverSfx = useHoverSfx('button');
    const clickSfx = useClickSfx(onToggle);
    return (
        <div className="lib-tweaks__row">
            <span>{label}</span>
            <button
                type="button"
                className={['lib-tweaks__toggle', value && 'on'].filter(Boolean).join(' ')}
                onClick={clickSfx}
                onMouseEnter={hoverSfx}
                aria-pressed={value}
                aria-label={label}
                data-sfx-hover="button"
            />
        </div>
    );
}

export default ToggleRow;
