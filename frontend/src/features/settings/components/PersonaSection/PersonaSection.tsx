import type { ReactElement } from 'react';
import { Label, Mono } from '@ui';

export function PersonaSection(): ReactElement {
    return (
        <div className="pb-1">
            <Label className="text-accent block mb-[14px] text-[10px] tracking-[0.15em] uppercase">
                Persona
            </Label>
            <div className="bg-black/20 border border-border rounded-[2px] px-[10px] py-2">
                <Mono size="sm" secondary as="p">
                    JARVIS belongs to:{' '}
                    <span className="text-accent">Johannes Aschenbrenner</span>
                </Mono>
                <Mono size="xs" muted as="p" className="block leading-[1.5] mt-1">
                    Salutation mode: random (Sir / Johannes)
                </Mono>
                <Mono size="xs" muted as="p" className="block leading-[1.5] mt-1">
                    Style: JARVIS — British formal. The Iron Man aesthetic is flavour only.
                </Mono>
            </div>
        </div>
    );
}

export default PersonaSection;
