import type { ReactElement } from 'react';
import { Mono } from '@ui';
import type { ToggleProps } from './Toggle.types';

/**
 * Toggle — JARVIS-styled boolean switch.
 * Knob slide transition is expressed via Tailwind transition-* utilities.
 */
export function Toggle({ checked, onChange, label, description }: ToggleProps): ReactElement {
    return (
        <div className="flex items-center justify-between gap-3 mb-[14px]">
            <div>
                <Mono size="md">{label}</Mono>
                {description !== undefined && (
                    <Mono size="xs" secondary as="p" className="mt-0.5 leading-[1.4]">
                        {description}
                    </Mono>
                )}
            </div>
            <button
                type="button"
                role="switch"
                aria-checked={checked}
                onClick={() => onChange(!checked)}
                className={[
                    'flex-shrink-0 w-9 h-[18px] relative cursor-pointer',
                    'border rounded-[2px] transition-all duration-[180ms]',
                    checked
                        ? 'border-accent bg-accent/25'
                        : 'border-border bg-black/30',
                ].join(' ')}
            >
                <span
                    className={[
                        'absolute top-0.5 w-3 h-3 rounded-[1px]',
                        'transition-all duration-[160ms]',
                        checked ? 'left-[18px] bg-accent' : 'left-0.5 bg-text-muted',
                    ].join(' ')}
                />
            </button>
        </div>
    );
}

export default Toggle;
