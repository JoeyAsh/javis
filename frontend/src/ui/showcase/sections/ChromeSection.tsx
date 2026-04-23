import { ReactElement } from 'react';
import { CornerBrackets } from '../../primitives/CornerBrackets';
import { Scanlines } from '../../primitives/Scanlines';
import { GridBackground } from '../../primitives/GridBackground';
import { GlowFrame } from '../../primitives/GlowFrame';
import { Reticle } from '../../primitives/Reticle';
import { ShowcaseCard } from '../ShowcaseCard';

export function ChromeSection(): ReactElement {
    return (
        <section id="chrome" className="flex flex-col gap-4">
            <div>
                <h2 className="text-[12px] text-text font-mono mb-1">
                    Chrome &amp; Embellishments
                </h2>
                <p className="text-[10px] text-text-secondary font-mono">
                    CornerBrackets · Scanlines · GridBackground · GlowFrame · Reticle
                </p>
            </div>
            <div className="grid grid-cols-3 gap-3">
                <ShowcaseCard
                    label="CORNER BRACKETS"
                    code={`<CornerBrackets>\n  <div>content</div>\n</CornerBrackets>`}
                >
                    <CornerBrackets className="p-4">
                        <div className="border border-border rounded-[2px] px-6 py-4 text-[10px] text-text-secondary font-mono">
                            CPU · 42%
                        </div>
                    </CornerBrackets>
                </ShowcaseCard>
                <ShowcaseCard
                    label="CORNER FOCUSED"
                    code={`<CornerBrackets focused>\n  …\n</CornerBrackets>`}
                >
                    <CornerBrackets focused className="p-4">
                        <div className="border border-border rounded-[2px] px-6 py-4 text-[10px] text-accent font-mono">
                            FOCUSED
                        </div>
                    </CornerBrackets>
                </ShowcaseCard>
                <ShowcaseCard
                    label="SCANLINES"
                    code={`<Scanlines sweep>\n  <div>content</div>\n</Scanlines>`}
                >
                    <Scanlines
                        sweep
                        className="border border-border rounded-[2px] px-6 py-4 w-full"
                    >
                        <div className="text-[10px] text-text-secondary font-mono uppercase tracking-[1px]">
                            NET · 12.3 Mb/s
                        </div>
                    </Scanlines>
                </ShowcaseCard>
                <ShowcaseCard
                    label="GLOW FRAME STATIC"
                    code={`<GlowFrame strong>\n  …\n</GlowFrame>`}
                >
                    <GlowFrame strong className="px-6 py-4">
                        <div className="text-[10px] text-accent font-mono">LISTENING…</div>
                    </GlowFrame>
                </ShowcaseCard>
                <ShowcaseCard
                    label="GLOW FRAME BREATHE"
                    code={`<GlowFrame breathe>\n  …\n</GlowFrame>`}
                >
                    <GlowFrame breathe className="px-6 py-4">
                        <div className="text-[22px] font-mono text-accent">●</div>
                    </GlowFrame>
                </ShowcaseCard>
                <ShowcaseCard label="RETICLE" code={`<Reticle size={16} />`}>
                    <div className="flex items-center gap-4">
                        <Reticle size={10} />
                        <Reticle size={14} />
                        <Reticle size={20} />
                    </div>
                </ShowcaseCard>
                <ShowcaseCard label="GRID BACKGROUND" code={`<GridBackground drift />`} dark>
                    <div className="relative w-full h-[80px] overflow-hidden rounded-[2px] border border-border">
                        <GridBackground gridSize={22} />
                        <span className="relative z-10 text-[9px] text-text-muted font-mono uppercase tracking-[1px]">
                            faint grid underlay
                        </span>
                    </div>
                </ShowcaseCard>
            </div>
        </section>
    );
}
