import type { ReactElement } from 'react';
import { StatusDock } from '../../compositions/StatusDock';
import { TopBar } from '../../primitives/TopBar';
import { CssOrb } from '../../orb/CssOrb';
import { Panel } from '../../primitives/Panel';
import { BrandMark } from '../../primitives/BrandMark';
import { Button } from '../../primitives/Button';
import type { AppOrbState } from '@common/types';
import type { ScopedHUDShellPreviewProps } from './ScopedHUDShellPreview.types';

export function ScopedHUDShellPreview({ idle, onIdleToggle }: ScopedHUDShellPreviewProps): ReactElement {
    const state: AppOrbState = 'idle';

    return (
        <div className={['hud-shell', idle && 'idle'].filter(Boolean).join(' ') + ' absolute inset-0'}>
            {/* Scene (non-fixed so it fills the preview box) */}
            <div className="lib-scene absolute inset-0" aria-hidden="true">
                <div className="lib-scene__grid" />
                <div className="lib-scene__scanlines" />
                <div className="lib-scene__vignette" />
                <div className="lib-scene__noise" />
                <div className="lib-scene__horizon" />
            </div>

            {/* Reactor scoped inside preview */}
            <div
                className="lib-reactor absolute -bottom-[360px] left-1/2 -translate-x-1/2"
                aria-hidden="true"
            />

            {/* TopBar — absolute inside preview */}
            <div className="absolute top-0 left-0 right-0 z-[30]">
                <TopBar
                    left={<BrandMark />}
                    center={
                        <span className="text-[9px] text-text-secondary font-mono uppercase tracking-[2px]">
                            JARVIS · HUD SHELL PREVIEW
                        </span>
                    }
                    right={
                        <Button variant="ghost" size="sm" onClick={onIdleToggle}>
                            {idle ? 'EXIT IDLE' : 'IDLE'}
                        </Button>
                    }
                />
            </div>

            {/* Orb — centered */}
            <div className="absolute inset-0 flex items-center justify-center z-0 pointer-events-none">
                <CssOrb state={state} particles />
            </div>

            {/* Sample panels */}
            <div className="hud-shell__children absolute inset-0">
                <div className="absolute top-14 left-5 w-[200px]">
                    <Panel title="SYSTEM">
                        <div className="text-[10px] text-text-secondary font-mono flex flex-col gap-1">
                            <span>CPU · 42%</span>
                            <span>MEM · 6.1 GB</span>
                            <span>UPTIME · 14h 22m</span>
                        </div>
                    </Panel>
                </div>
                <div className="absolute top-14 right-5 w-[200px]">
                    <Panel title="NOW PLAYING">
                        <div className="text-[10px] text-text-secondary font-mono flex flex-col gap-1">
                            <span className="text-text">Back in Black</span>
                            <span>AC/DC</span>
                        </div>
                    </Panel>
                </div>
            </div>

            {/* Status Dock — absolute bottom-center inside preview */}
            <div className="absolute left-1/2 -translate-x-1/2 bottom-6 z-[25]">
                <StatusDock state={state} />
            </div>

            {/* Viewport corner marks scoped */}
            {(['tl', 'tr', 'bl', 'br'] as const).map((pos) => (
                <span
                    key={pos}
                    className={`lib-viewport-corner ${pos} absolute`}
                    aria-hidden="true"
                />
            ))}
        </div>
    );
}

export default ScopedHUDShellPreview;
