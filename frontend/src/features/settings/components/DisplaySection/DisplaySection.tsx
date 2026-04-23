import type { ReactElement } from 'react';
import { Label, Mono } from '@ui';
import type { DisplaySectionProps } from './DisplaySection.types';

export function DisplaySection({
    panelOpacity,
    onPanelOpacityChange,
    orbStyle,
    onOrbStyleChange,
}: DisplaySectionProps): ReactElement {
    return (
        <div className="border-b border-border pb-5 mb-5">
            <Label className="text-accent block mb-[14px] text-[10px] tracking-[0.15em] uppercase">
                Display
            </Label>

            <Label htmlFor="sv-opacity-slider" className="block mb-1">
                Panel opacity — {Math.round(panelOpacity * 100)}%
            </Label>
            <input
                id="sv-opacity-slider"
                type="range"
                min={0.5}
                max={1.0}
                step={0.01}
                value={panelOpacity}
                onChange={(e) => onPanelOpacityChange(parseFloat(e.target.value))}
                className="w-full cursor-pointer mt-1 accent-accent"
            />

            <div className="mt-[14px]">
                <Label className="block mb-1">Orb Style</Label>
                <div className="flex gap-2 mt-1.5">
                    <OrbOption
                        active={orbStyle === 'css'}
                        onClick={() => onOrbStyleChange('css')}
                        title="CSS / DOM"
                        description="Rings, pulses, particles — lightweight"
                    />
                    <OrbOption
                        active={orbStyle === 'threejs'}
                        onClick={() => onOrbStyleChange('threejs')}
                        title="Three.js"
                        description="2000 particles, WebGL — GPU-intensive"
                    />
                </div>
            </div>
        </div>
    );
}

interface OrbOptionProps {
    active: boolean;
    onClick: () => void;
    title: string;
    description: string;
}

function OrbOption({ active, onClick, title, description }: OrbOptionProps): ReactElement {
    return (
        <button
            type="button"
            onClick={onClick}
            className={[
                'flex-1 flex flex-col gap-0.5 px-[10px] py-2 rounded-[2px] cursor-pointer text-left',
                'border transition-all duration-[150ms]',
                active
                    ? 'border-accent bg-accent/10'
                    : 'border-border bg-black/20 hover:border-accent/50 hover:bg-accent/5',
            ].join(' ')}
        >
            <Mono size="sm">{title}</Mono>
            <Mono size="xs" muted>{description}</Mono>
        </button>
    );
}

export default DisplaySection;
