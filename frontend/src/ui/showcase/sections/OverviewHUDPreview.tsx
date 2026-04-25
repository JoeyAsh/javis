import type { ReactElement } from 'react';
import { TopBar } from '../../primitives/TopBar';
import { BrandMark } from '../../primitives/BrandMark';
import { CssOrb } from '../../orb/CssOrb';
import { Panel } from '../../primitives/Panel';
import { StatusDock } from '../../compositions/StatusDock';
import { Label } from '../../primitives/Label';
import type { OverviewHUDPreviewProps } from './OverviewHUDPreview.types';

export function OverviewHUDPreview({ state }: OverviewHUDPreviewProps): ReactElement {
    return (
        <div className="absolute inset-0 bg-[var(--bg)]">
            {/* Scene layer */}
            <div className="lib-scene absolute inset-0" aria-hidden="true">
                <div className="lib-scene__grid" />
                <div className="lib-scene__scanlines" />
                <div className="lib-scene__vignette" />
                <div className="lib-scene__noise" />
                <div className="lib-scene__horizon" />
            </div>

            {/* Reactor */}
            <div
                className="lib-reactor absolute -bottom-[360px] left-1/2 -translate-x-1/2"
                aria-hidden="true"
            />

            {/* TopBar */}
            <div className="absolute top-0 left-0 right-0 z-[30]">
                <TopBar
                    left={<BrandMark />}
                    center={
                        <span className="text-[9px] text-text-secondary font-mono uppercase tracking-[2px]">
                            JARVIS · HUD PREVIEW
                        </span>
                    }
                    right={
                        <span className="text-[8px] text-text-muted font-mono uppercase tracking-[1px]">
                            N 48.21 · E 16.37
                        </span>
                    }
                />
            </div>

            {/* Orb centered */}
            <div className="absolute inset-0 flex items-center justify-center z-0 pointer-events-none">
                <CssOrb state={state} particles />
            </div>

            {/* Window shells */}
            <div className="absolute top-14 left-5 w-[220px] z-[10]">
                <Panel title="SYSTEM" ix="◈">
                    <Label dim>CPU · RAM · UPTIME</Label>
                </Panel>
            </div>
            <div className="absolute top-14 right-5 w-[220px] z-[10]">
                <Panel title="TRANSCRIPT" ix="▸">
                    <Label dim>Awaiting input...</Label>
                </Panel>
            </div>
            <div className="absolute bottom-20 left-5 w-[220px] z-[10]">
                <Panel title="AGENDA" ix="▦">
                    <Label dim>No events</Label>
                </Panel>
            </div>

            {/* Status Dock */}
            <div className="absolute left-1/2 -translate-x-1/2 bottom-6 z-[25]">
                <StatusDock state={state} />
            </div>

            {/* Viewport corners */}
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

export default OverviewHUDPreview;
