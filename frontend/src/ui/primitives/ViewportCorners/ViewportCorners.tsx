import { type ReactElement } from 'react';
import type { ViewportCornersProps } from './ViewportCorners.types';
import './ViewportCorners.css';

export function ViewportCorners({ className }: ViewportCornersProps): ReactElement {
    const corners: ReadonlyArray<'tl' | 'tr' | 'bl' | 'br'> = ['tl', 'tr', 'bl', 'br'];

    return (
        <>
            {corners.map((pos) => (
                <span
                    key={pos}
                    className={['lib-viewport-corner', pos, className].filter(Boolean).join(' ')}
                    aria-hidden="true"
                />
            ))}
        </>
    );
}

export default ViewportCorners;
