import { ReactElement } from 'react';

interface Swatch {
    name: string;
    value: string;
    cssVar: string;
    border?: boolean;
}

const SWATCHES: Swatch[] = [
    { name: 'bg', value: '#050508', cssVar: '--bg', border: true },
    { name: 'surface', value: '#0d0d14', cssVar: '--surface' },
    { name: 'surface-raised', value: '#12121c', cssVar: '--surface-raised' },
    { name: 'border', value: '#1a1a2e', cssVar: '--border' },
    { name: 'border-bright', value: '#2a3d4f', cssVar: '--border-bright' },
    { name: 'accent', value: '#4ca8e8', cssVar: '--accent' },
    { name: 'accent-bright', value: '#6ec4ff', cssVar: '--accent-bright' },
    { name: 'accent-speak', value: '#5ab8f0', cssVar: '--accent-speak' },
    { name: 'accent-dim', value: '#2d6aa1', cssVar: '--accent-dim' },
    { name: 'text', value: '#e8f4ff', cssVar: '--text' },
    { name: 'text-secondary', value: '#6b8fa8', cssVar: '--text-secondary' },
    { name: 'text-muted', value: '#2a3d4f', cssVar: '--text-muted' },
    { name: 'warning', value: '#e8b24c', cssVar: '--warning' },
    { name: 'error', value: '#e85a5a', cssVar: '--error' },
    { name: 'success', value: '#4ce8a8', cssVar: '--success' },
];

export function ColorsSection(): ReactElement {
    return (
        <section id="colors" className="flex flex-col gap-4">
            <div>
                <h2 className="text-[12px] text-text font-mono mb-1">Colors</h2>
                <p className="text-[10px] text-text-secondary font-mono">
                    3 backgrounds · 3 blue accents · 3 text tiers · semantic states
                </p>
            </div>
            <div className="grid grid-cols-5 gap-[10px]">
                {SWATCHES.map((sw) => (
                    <div key={sw.cssVar} className="border border-border rounded-[2px] p-[10px]">
                        <div
                            className="h-[42px] rounded-[2px] mb-2"
                            style={{
                                background: `var(${sw.cssVar})`,
                                border: sw.border ? '1px solid var(--border)' : undefined,
                            }}
                        />
                        <div className="text-[10px] text-text font-mono leading-[1.3]">
                            {sw.name}
                        </div>
                        <div className="text-[9px] text-text-muted font-mono uppercase tracking-[1px] mt-[2px]">
                            {sw.value}
                        </div>
                    </div>
                ))}
            </div>
        </section>
    );
}
