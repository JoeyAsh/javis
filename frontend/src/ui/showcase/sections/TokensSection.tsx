import { ReactElement } from 'react';
import { Label } from '../../primitives/Label';
import { Metric } from '../../primitives/Metric';
import { Mono } from '../../primitives/Mono';
import { BrandMark } from '../../primitives/BrandMark';
import { ShowcaseCard } from '../ShowcaseCard';

/* ---- Color swatches ---- */

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

/* ---- Spacing scale ---- */

const SPACING: { label: string; size: number }[] = [
    { label: '4', size: 4 },
    { label: '8', size: 8 },
    { label: '12', size: 12 },
    { label: '16', size: 16 },
    { label: '24', size: 24 },
    { label: '32', size: 32 },
    { label: '48', size: 48 },
    { label: '64', size: 64 },
];

/* ---- Shadow samples ---- */

const SHADOWS: { label: string; shadow: string }[] = [
    { label: 'glow', shadow: 'var(--glow)' },
    { label: 'glow-strong', shadow: 'var(--glow-strong)' },
    { label: 'glow-inner', shadow: 'inset 0 0 12px rgba(76,168,232,0.35)' },
    { label: 'glow-warn', shadow: '0 0 8px rgba(232,178,76,0.6)' },
    { label: 'glow-error', shadow: '0 0 8px rgba(232,90,90,0.6)' },
];

export function TokensSection(): ReactElement {
    return (
        <section id="tokens" className="flex flex-col gap-8">
            <div>
                <h2 className="text-[12px] text-text font-mono mb-1">TOKENS</h2>
                <p className="text-[10px] text-text-secondary font-mono">
                    Colors · Typography · Spacing · Radius · Shadows — single source of truth in
                    index.css
                </p>
            </div>

            {/* Colors */}
            <div className="flex flex-col gap-3">
                <span className="text-[9px] uppercase tracking-[2px] font-mono text-text-secondary">
                    Colors
                </span>
                <div className="grid grid-cols-5 gap-[10px]">
                    {SWATCHES.map((sw) => (
                        <div key={sw.cssVar} className="border border-border p-[10px]">
                            <div
                                className="h-[42px] mb-2"
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
            </div>

            {/* Typography */}
            <div className="flex flex-col gap-3">
                <span className="text-[9px] uppercase tracking-[2px] font-mono text-text-secondary">
                    Typography
                </span>
                <div className="grid grid-cols-3 gap-3">
                    <ShowcaseCard label="LABEL DEFAULT" code={`<Label>CPU USAGE</Label>`}>
                        <Label>CPU USAGE</Label>
                    </ShowcaseCard>
                    <ShowcaseCard label="LABEL DIM" code={`<Label dim>OFFLINE</Label>`}>
                        <Label dim>OFFLINE</Label>
                    </ShowcaseCard>
                    <ShowcaseCard label="METRIC VALUE" code={`<Metric value={42} unit="%" />`}>
                        <Metric value={42} unit="%" />
                    </ShowcaseCard>
                    <ShowcaseCard label="METRIC WARN" code={`<Metric value={87} unit="°C" warn />`}>
                        <Metric value={87} unit="°C" warn />
                    </ShowcaseCard>
                    <ShowcaseCard
                        label="MONO SIZES"
                        code={`<Mono size="sm" secondary>12.3 Mb/s</Mono>`}
                    >
                        <div className="flex flex-col gap-1 items-center">
                            <Mono size="xs" muted>
                                xs · 9px muted
                            </Mono>
                            <Mono size="sm" secondary>
                                sm · 10px secondary
                            </Mono>
                            <Mono size="md">md · 11px text</Mono>
                            <Mono size="lg">lg · 13px text</Mono>
                        </div>
                    </ShowcaseCard>
                    <ShowcaseCard label="BRAND MARK" code={`<BrandMark sub />`}>
                        <BrandMark sub />
                    </ShowcaseCard>
                </div>
            </div>

            {/* Spacing scale */}
            <div className="flex flex-col gap-3">
                <span className="text-[9px] uppercase tracking-[2px] font-mono text-text-secondary">
                    Spacing Scale (px)
                </span>
                <div
                    className="flex items-end gap-3 border border-border p-4"
                    style={{ background: 'rgba(13,13,20,0.75)' }}
                >
                    {SPACING.map(({ label, size }) => (
                        <div key={label} className="flex flex-col items-center gap-1">
                            <div
                                style={{
                                    width: size,
                                    height: size,
                                    background: 'var(--accent)',
                                    opacity: 0.5,
                                }}
                            />
                            <span className="text-[8px] text-text-muted font-mono">{label}</span>
                        </div>
                    ))}
                </div>
            </div>

            {/* Radius scale */}
            <div className="flex flex-col gap-3">
                <span className="text-[9px] uppercase tracking-[2px] font-mono text-text-secondary">
                    Radius Scale
                </span>
                <div className="flex items-center gap-4">
                    {[
                        { label: '2px (sharp)', r: 2 },
                        { label: '4px (max allowed)', r: 4 },
                        { label: '50% (pill/circle)', r: 999 },
                    ].map(({ label, r }) => (
                        <div key={label} className="flex flex-col items-center gap-2">
                            <div
                                style={{
                                    width: 80,
                                    height: 32,
                                    background: 'var(--surface-raised)',
                                    border: '1px solid var(--border)',
                                    borderRadius: r,
                                }}
                            />
                            <span className="text-[8px] text-text-muted font-mono">{label}</span>
                        </div>
                    ))}
                </div>
            </div>

            {/* Shadow scale */}
            <div className="flex flex-col gap-3">
                <span className="text-[9px] uppercase tracking-[2px] font-mono text-text-secondary">
                    Shadows
                </span>
                <div className="flex flex-wrap gap-4">
                    {SHADOWS.map(({ label, shadow }) => (
                        <div key={label} className="flex flex-col items-center gap-2">
                            <div
                                style={{
                                    width: 120,
                                    height: 40,
                                    background: 'var(--surface-raised)',
                                    border: '1px solid var(--border)',
                                    boxShadow: shadow,
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                }}
                            >
                                <span className="text-[8px] text-accent font-mono uppercase tracking-[1px]">
                                    {label}
                                </span>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </section>
    );
}

export default TokensSection;
