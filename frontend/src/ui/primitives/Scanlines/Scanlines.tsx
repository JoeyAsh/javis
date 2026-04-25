import { ReactElement } from 'react';
import { cx } from '@common/utils/cx';
import type { ScanlinesProps } from './Scanlines.types';

export function Scanlines({ children, className, sweep = false }: ScanlinesProps): ReactElement {
    return (
        <div className={cx('relative overflow-hidden', className)}>
            {children}
            {/* scanline overlay — repeating-linear-gradient + mix-blend-mode require inline style */}
            <span
                aria-hidden
                className="pointer-events-none absolute inset-0 motion-reduce:hidden z-[1]"
                style={{
                    background:
                        'repeating-linear-gradient(to bottom, transparent 0, transparent 2px, rgba(76,168,232,0.035) 2px, rgba(76,168,232,0.035) 3px)',
                    mixBlendMode: 'screen',
                } as React.CSSProperties}
            />
            {/* optional data-sweep shimmer */}
            {sweep && (
                <span
                    aria-hidden
                    className="pointer-events-none absolute inset-0 overflow-hidden motion-reduce:hidden z-[2]"
                >
                    <span
                        className="absolute top-0 bottom-0 w-[40%]"
                        style={{
                            background:
                                'linear-gradient(90deg, transparent, rgba(76,168,232,0.25), transparent)',
                            animation: 'jlib-sweep-x 3.2s linear infinite',
                        } as React.CSSProperties}
                    />
                </span>
            )}
        </div>
    );
}

export default Scanlines;
