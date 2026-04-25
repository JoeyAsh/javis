import { type ReactElement } from 'react';
import { StarField } from '../StarField/StarField';
import type { SceneProps } from './Scene.types';

export function Scene({
    grid = true,
    stars = true,
    scanlines = true,
    className,
}: SceneProps): ReactElement {
    return (
        <div className={['lib-scene', className].filter(Boolean).join(' ')} aria-hidden="true">
            {grid && <div className="lib-scene__grid" />}
            {scanlines && <div className="lib-scene__scanlines" />}
            <div className="lib-scene__vignette" />
            <div className="lib-scene__noise" />
            <div className="lib-scene__horizon" />
            {stars && <StarField />}
        </div>
    );
}

export default Scene;
