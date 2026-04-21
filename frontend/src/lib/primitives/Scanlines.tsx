import { ReactElement, ReactNode } from 'react';
import '../lib.css';

export interface ScanlinesProps {
    children: ReactNode;
    className?: string;
    sweep?: boolean;
}

function cn(...parts: (string | undefined | false)[]): string {
    return parts.filter(Boolean).join(' ');
}

export function Scanlines({ children, className, sweep = false }: ScanlinesProps): ReactElement {
    return (
        <div className={cn('relative overflow-hidden', className)}>
            {children}
            {/* scanline overlay */}
            <span
                aria-hidden
                className="pointer-events-none absolute inset-0 motion-reduce:hidden"
                style={{
                    background:
                        'repeating-linear-gradient(to bottom, transparent 0, transparent 2px, rgba(76,168,232,0.035) 2px, rgba(76,168,232,0.035) 3px)',
                    mixBlendMode: 'screen',
                    zIndex: 1,
                }}
            />
            {/* optional data-sweep shimmer */}
            {sweep && (
                <span
                    aria-hidden
                    className="pointer-events-none absolute inset-0 overflow-hidden motion-reduce:hidden"
                    style={{ zIndex: 2 }}
                >
                    <span
                        className="absolute top-0 bottom-0"
                        style={{
                            width: '40%',
                            background:
                                'linear-gradient(90deg, transparent, rgba(76,168,232,0.25), transparent)',
                            animation: 'jlib-sweep-x 3.2s linear infinite',
                        }}
                    />
                </span>
            )}
        </div>
    );
}

export default Scanlines;
