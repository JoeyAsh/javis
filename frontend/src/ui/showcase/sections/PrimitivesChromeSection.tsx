import { ReactElement } from 'react';
import { CornerBrackets } from '../../primitives/CornerBrackets';
import { Scanlines } from '../../primitives/Scanlines';
import { GridBackground } from '../../primitives/GridBackground';
import { GlowFrame } from '../../primitives/GlowFrame';
import { Reticle } from '../../primitives/Reticle';
import { LightTrace } from '../../primitives/LightTrace';
import { PanelBloom } from '../../primitives/PanelBloom';
import { PanelRails } from '../../primitives/PanelRails';
import { StarField } from '../../primitives/StarField';
import { Reactor } from '../../primitives/Reactor';
import { ShowcaseCard } from '../ShowcaseCard';

export function PrimitivesChromeSection(): ReactElement {
    return (
        <section id="chrome" className="flex flex-col gap-8">
            <div>
                <h2 className="text-[12px] text-text font-mono mb-1">PRIMITIVES — Chrome</h2>
                <p className="text-[10px] text-text-secondary font-mono">
                    CornerBrackets · LightTrace · PanelBloom · PanelRails · Scanlines ·
                    GridBackground · GlowFrame · Reticle · ViewportCorners · StarField · Reactor ·
                    Scene
                </p>
            </div>

            <div className="grid grid-cols-3 gap-3">
                {/* CornerBrackets default */}
                <ShowcaseCard
                    label="CORNER BRACKETS"
                    code={`<CornerBrackets>\n  <div>content</div>\n</CornerBrackets>`}
                >
                    <CornerBrackets className="p-4">
                        <div className="border border-border px-6 py-4 text-[10px] text-text-secondary font-mono">
                            CPU · 42%
                        </div>
                    </CornerBrackets>
                </ShowcaseCard>

                {/* CornerBrackets focused */}
                <ShowcaseCard
                    label="CORNER FOCUSED"
                    code={`<CornerBrackets focused>\n  …\n</CornerBrackets>`}
                >
                    <CornerBrackets focused className="p-4">
                        <div className="border border-border px-6 py-4 text-[10px] text-accent font-mono">
                            FOCUSED
                        </div>
                    </CornerBrackets>
                </ShowcaseCard>

                {/* LightTrace */}
                <ShowcaseCard label="LIGHT TRACE" code={`<LightTrace />`} dark>
                    <div
                        className="relative w-full overflow-hidden border border-border"
                        style={{ height: 40 }}
                    >
                        <LightTrace />
                    </div>
                </ShowcaseCard>

                {/* PanelBloom */}
                <ShowcaseCard label="PANEL BLOOM (active)" code={`<PanelBloom active />`} dark>
                    <div className="relative w-full border border-accent" style={{ height: 60 }}>
                        <PanelBloom active />
                        <span className="relative z-10 text-[9px] text-accent font-mono flex items-center justify-center h-full uppercase tracking-[1px]">
                            bloom active
                        </span>
                    </div>
                </ShowcaseCard>

                {/* PanelRails */}
                <ShowcaseCard label="PANEL RAILS" code={`<PanelRails visible />`} dark>
                    <div className="relative w-full border border-border" style={{ height: 60 }}>
                        <PanelRails visible />
                        <span className="relative z-10 text-[9px] text-text-secondary font-mono flex items-center justify-center h-full uppercase tracking-[1px]">
                            rails
                        </span>
                    </div>
                </ShowcaseCard>

                {/* Scanlines */}
                <ShowcaseCard
                    label="SCANLINES"
                    code={`<Scanlines sweep>\n  <div>content</div>\n</Scanlines>`}
                >
                    <Scanlines sweep className="border border-border px-6 py-4 w-full">
                        <div className="text-[10px] text-text-secondary font-mono uppercase tracking-[1px]">
                            NET · 12.3 Mb/s
                        </div>
                    </Scanlines>
                </ShowcaseCard>

                {/* GlowFrame static */}
                <ShowcaseCard
                    label="GLOW FRAME STATIC"
                    code={`<GlowFrame strong>\n  …\n</GlowFrame>`}
                >
                    <GlowFrame strong className="px-6 py-4">
                        <div className="text-[10px] text-accent font-mono">LISTENING…</div>
                    </GlowFrame>
                </ShowcaseCard>

                {/* GlowFrame breathe */}
                <ShowcaseCard
                    label="GLOW FRAME BREATHE"
                    code={`<GlowFrame breathe>\n  …\n</GlowFrame>`}
                >
                    <GlowFrame breathe className="px-6 py-4">
                        <div className="text-[22px] font-mono text-accent">●</div>
                    </GlowFrame>
                </ShowcaseCard>

                {/* Reticle sizes */}
                <ShowcaseCard label="RETICLE SIZES" code={`<Reticle size={16} />`}>
                    <div className="flex items-center gap-4">
                        <Reticle size={10} />
                        <Reticle size={14} />
                        <Reticle size={20} />
                    </div>
                </ShowcaseCard>

                {/* GridBackground */}
                <ShowcaseCard label="GRID BACKGROUND" code={`<GridBackground drift />`} dark>
                    <div
                        className="relative w-full overflow-hidden border border-border"
                        style={{ height: 80 }}
                    >
                        <GridBackground gridSize={22} />
                        <span className="relative z-10 text-[9px] text-text-muted font-mono uppercase tracking-[1px] flex items-center justify-center h-full">
                            faint grid underlay
                        </span>
                    </div>
                </ShowcaseCard>

                {/* StarField */}
                <ShowcaseCard label="STAR FIELD" code={`<StarField count={40} />`} dark>
                    <div
                        className="relative w-full overflow-hidden border border-border"
                        style={{ height: 80, background: '#050508' }}
                    >
                        <StarField count={30} />
                        <span className="relative z-10 text-[9px] text-text-muted font-mono uppercase tracking-[1px] flex items-center justify-center h-full">
                            star field
                        </span>
                    </div>
                </ShowcaseCard>

                {/* ViewportCorners — fixed position note */}
                <ShowcaseCard label="VIEWPORT CORNERS" code={`<ViewportCorners />`} dark>
                    <div
                        className="relative w-full border border-border overflow-hidden"
                        style={{ height: 80, background: 'rgba(5,5,8,0.95)' }}
                    >
                        {(['tl', 'tr', 'bl', 'br'] as const).map((pos) => (
                            <span
                                key={pos}
                                className={`lib-viewport-corner ${pos}`}
                                style={{ position: 'absolute' }}
                                aria-hidden="true"
                            />
                        ))}
                        <span className="relative z-10 text-[9px] text-text-muted font-mono uppercase tracking-[1px] flex items-center justify-center h-full">
                            scoped demo — in production: fixed + full viewport
                        </span>
                    </div>
                </ShowcaseCard>
            </div>

            {/* Reactor — full-width card, scoped */}
            <div className="flex flex-col gap-2">
                <span className="text-[9px] uppercase tracking-[2px] font-mono text-text-secondary">
                    Reactor (scoped · normally position:fixed)
                </span>
                <div
                    className="relative border border-border overflow-hidden"
                    style={{ height: 200, background: '#050508' }}
                >
                    <div
                        style={{
                            position: 'absolute',
                            bottom: -320,
                            left: '50%',
                            transform: 'translateX(-50%)',
                        }}
                    >
                        <Reactor />
                    </div>
                    <span className="text-[9px] text-text-muted font-mono uppercase tracking-[1px] flex items-end justify-center pb-3 h-full relative z-10">
                        ambient glow base under orb
                    </span>
                </div>
            </div>

            {/* Scene — full-width */}
            <div className="flex flex-col gap-2">
                <span className="text-[9px] uppercase tracking-[2px] font-mono text-text-secondary">
                    Scene (scoped · normally position:fixed)
                </span>
                <div
                    className="relative border border-border overflow-hidden"
                    style={{ height: 200 }}
                >
                    {/* Render scene sub-elements manually so position:fixed doesn't escape container */}
                    <div
                        aria-hidden="true"
                        style={{
                            position: 'absolute',
                            inset: 0,
                            overflow: 'hidden',
                            background:
                                'radial-gradient(ellipse at 50% 52%, #0a1220 0%, #05080f 45%, #020206 100%)',
                        }}
                    >
                        <div className="lib-scene__grid" />
                        <div className="lib-scene__scanlines" />
                        <div className="lib-scene__vignette" />
                        <div className="lib-scene__noise" />
                        <div className="lib-scene__horizon" />
                        <StarField count={20} />
                    </div>
                    <span className="text-[9px] text-text-muted font-mono uppercase tracking-[1px] flex items-center justify-center h-full relative z-10">
                        grid + stars + scanlines + vignette + horizon
                    </span>
                </div>
            </div>
        </section>
    );
}

export default PrimitivesChromeSection;
