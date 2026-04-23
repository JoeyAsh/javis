import { ReactElement } from 'react';
import {
    Mic,
    MicOff,
    Settings,
    RotateCcw,
    Power,
    Play,
    Pause,
    Zap,
    Volume2,
    Cpu,
    Network,
    CheckCircle,
    AlertTriangle,
    X,
    Maximize2,
    Minimize2,
    ChevronLeft,
    ChevronRight,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { Icon } from '../../primitives/Icon';
import { ShowcaseCard } from '../ShowcaseCard';

interface IconEntry {
    name: string;
    icon: LucideIcon;
}

const ICONS: IconEntry[] = [
    { name: 'mic', icon: Mic },
    { name: 'mute', icon: MicOff },
    { name: 'settings', icon: Settings },
    { name: 'reset', icon: RotateCcw },
    { name: 'power', icon: Power },
    { name: 'play', icon: Play },
    { name: 'pause', icon: Pause },
    { name: 'bolt', icon: Zap },
    { name: 'volume', icon: Volume2 },
    { name: 'cpu', icon: Cpu },
    { name: 'network', icon: Network },
    { name: 'check', icon: CheckCircle },
    { name: 'warning', icon: AlertTriangle },
    { name: 'close', icon: X },
    { name: 'maximize', icon: Maximize2 },
    { name: 'minimize', icon: Minimize2 },
    { name: 'prev', icon: ChevronLeft },
    { name: 'next', icon: ChevronRight },
];

export function IconsSection(): ReactElement {
    return (
        <section id="icons" className="flex flex-col gap-4">
            <div>
                <h2 className="text-[12px] text-text font-mono mb-1">Icons</h2>
                <p className="text-[10px] text-text-secondary font-mono">
                    lucide-react · stroke-width 1.75 · sizes sm 12 / md 14 / lg 16
                </p>
            </div>
            <ShowcaseCard label="ICON GRID" code={`<Icon icon={Mic} size="md" />`}>
                <div className="grid grid-cols-9 gap-3 w-full">
                    {ICONS.map(({ name, icon }) => (
                        <div
                            key={name}
                            className="flex flex-col items-center gap-1 p-2 border border-border rounded-[2px] text-accent"
                        >
                            <Icon icon={icon} size="lg" />
                            <span className="text-[8px] text-text-muted font-mono uppercase tracking-[1px]">
                                {name}
                            </span>
                        </div>
                    ))}
                </div>
            </ShowcaseCard>
            <div className="grid grid-cols-3 gap-3">
                <ShowcaseCard label="ICON SM 12px" code={`<Icon icon={Mic} size="sm" />`}>
                    <Icon icon={Mic} size="sm" className="text-accent" />
                </ShowcaseCard>
                <ShowcaseCard label="ICON MD 14px" code={`<Icon icon={Mic} size="md" />`}>
                    <Icon icon={Mic} size="md" className="text-accent" />
                </ShowcaseCard>
                <ShowcaseCard label="ICON LG 16px" code={`<Icon icon={Mic} size="lg" />`}>
                    <Icon icon={Mic} size="lg" className="text-accent" />
                </ShowcaseCard>
            </div>
        </section>
    );
}
