import type { ReactElement } from 'react';
import { useClickSfx, useHoverSfx } from '@core/audio';
import type { SwatchButtonProps } from './Tweaks.types';

export function SwatchButton({ hue, active, onSelect }: SwatchButtonProps): ReactElement {
    const hoverSfx = useHoverSfx('button');
    const clickSfx = useClickSfx(onSelect);
    return (
        <button
            type="button"
            className={['lib-tweaks__swatch', active && 'active'].filter(Boolean).join(' ')}
            style={{ background: `oklch(0.72 0.14 ${hue})` } as React.CSSProperties}
            onClick={clickSfx}
            onMouseEnter={hoverSfx}
            aria-label={`Hue ${hue}`}
            data-sfx-hover="button"
        />
    );
}

export default SwatchButton;
