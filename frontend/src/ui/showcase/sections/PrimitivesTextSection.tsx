import { ReactElement } from 'react';
import { Button } from '../../primitives/Button';
import { Label } from '../../primitives/Label';
import { Metric } from '../../primitives/Metric';
import { Mono } from '../../primitives/Mono';
import { BrandMark } from '../../primitives/BrandMark';
import { Pill } from '../../primitives/Pill';
import { ProgressBar } from '../../primitives/ProgressBar';
import { Sparkline } from '../../primitives/Sparkline';
import { Icon } from '../../primitives/Icon';
import { ShowcaseCard } from '../ShowcaseCard';
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
import type { IconEntry } from './IconsSection.types';

const CPU_DATA = [18, 16, 14, 12, 14, 10, 8, 11, 6, 9, 5, 7, 11, 8, 6];
const TEMP_DATA = [14, 13, 11, 12, 9, 7, 5, 4, 3, 2, 1, 2, 4, 6, 8];

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

export function PrimitivesTextSection(): ReactElement {
    return (
        <section id="primitives-text" className="flex flex-col gap-8">
            <div>
                <h2 className="text-[12px] text-text font-mono mb-1">
                    PRIMITIVES — Text &amp; Data
                </h2>
                <p className="text-[10px] text-text-secondary font-mono">
                    Button · Label · Metric · Mono · BrandMark · Pill · ProgressBar · Sparkline ·
                    Icon
                </p>
            </div>

            {/* Buttons */}
            <div className="flex flex-col gap-3">
                <span className="text-[9px] uppercase tracking-[2px] font-mono text-text-secondary">
                    Buttons
                </span>
                <div className="grid grid-cols-3 gap-3">
                    <ShowcaseCard
                        label="PRIMARY MD"
                        code={`<Button variant="primary">CONNECT</Button>`}
                    >
                        <Button variant="primary">CONNECT</Button>
                    </ShowcaseCard>
                    <ShowcaseCard label="SECONDARY MD" code={`<Button>RESET</Button>`}>
                        <Button>RESET</Button>
                    </ShowcaseCard>
                    <ShowcaseCard label="GHOST MD" code={`<Button variant="ghost">CANCEL</Button>`}>
                        <Button variant="ghost">CANCEL</Button>
                    </ShowcaseCard>
                    <ShowcaseCard label="DANGER MD" code={`<Button variant="danger">STOP</Button>`}>
                        <Button variant="danger">STOP</Button>
                    </ShowcaseCard>
                    <ShowcaseCard
                        label="PRIMARY SM"
                        code={`<Button variant="primary" size="sm">CONNECT</Button>`}
                    >
                        <Button variant="primary" size="sm">
                            CONNECT
                        </Button>
                    </ShowcaseCard>
                    <ShowcaseCard label="DISABLED" code={`<Button disabled>DISABLED</Button>`}>
                        <Button disabled>DISABLED</Button>
                    </ShowcaseCard>
                </div>
            </div>

            {/* Labels, Metric, Mono, BrandMark */}
            <div className="flex flex-col gap-3">
                <span className="text-[9px] uppercase tracking-[2px] font-mono text-text-secondary">
                    Labels · Metric · Mono · BrandMark
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
                                xs · 9px
                            </Mono>
                            <Mono size="sm" secondary>
                                sm · 10px
                            </Mono>
                            <Mono size="md">md · 11px</Mono>
                            <Mono size="lg">lg · 13px</Mono>
                        </div>
                    </ShowcaseCard>
                    <ShowcaseCard label="BRAND MARK" code={`<BrandMark sub />`}>
                        <BrandMark sub />
                    </ShowcaseCard>
                </div>
            </div>

            {/* Pill */}
            <div className="flex flex-col gap-3">
                <span className="text-[9px] uppercase tracking-[2px] font-mono text-text-secondary">
                    Pill
                </span>
                <ShowcaseCard label="PILL VARIANTS" code={`<Pill variant="ok">ONLINE</Pill>`}>
                    <div className="flex flex-wrap gap-2 justify-center">
                        <Pill>DEFAULT</Pill>
                        <Pill variant="ok">ONLINE</Pill>
                        <Pill variant="warn">WARN</Pill>
                        <Pill variant="err">ERROR</Pill>
                        <Pill variant="info">INFO</Pill>
                    </div>
                </ShowcaseCard>
            </div>

            {/* ProgressBar + Sparkline */}
            <div className="flex flex-col gap-3">
                <span className="text-[9px] uppercase tracking-[2px] font-mono text-text-secondary">
                    ProgressBar · Sparkline
                </span>
                <div className="grid grid-cols-3 gap-3">
                    <ShowcaseCard
                        label="PROGRESS BAR"
                        code={`<ProgressBar value={0.42} />\n<ProgressBar value={0.7} variant="bright" />`}
                    >
                        <div className="w-full flex flex-col gap-2">
                            <ProgressBar value={0.42} aria-label="CPU" />
                            <ProgressBar value={0.7} variant="bright" aria-label="Memory" />
                            <ProgressBar value={0.15} variant="warn" aria-label="Disk" />
                            <ProgressBar value={0.55} height="normal" aria-label="Progress" />
                        </div>
                    </ShowcaseCard>
                    <ShowcaseCard label="SPARKLINE ACCENT" code={`<Sparkline data={cpuData} />`}>
                        <div className="w-full">
                            <div className="flex justify-between mb-1">
                                <Label>CPU</Label>
                                <Metric value={42} unit="%" />
                            </div>
                            <Sparkline data={CPU_DATA} variant="accent" />
                        </div>
                    </ShowcaseCard>
                    <ShowcaseCard
                        label="SPARKLINE WARN"
                        code={`<Sparkline data={tempData} variant="warn" />`}
                    >
                        <div className="w-full">
                            <div className="flex justify-between mb-1">
                                <Label>TEMP</Label>
                                <Metric value={87} unit="°C" warn />
                            </div>
                            <Sparkline data={TEMP_DATA} variant="warn" />
                        </div>
                    </ShowcaseCard>
                </div>
            </div>

            {/* Icons */}
            <div className="flex flex-col gap-3">
                <span className="text-[9px] uppercase tracking-[2px] font-mono text-text-secondary">
                    Icons (lucide-react)
                </span>
                <ShowcaseCard
                    label="ICON GRID — lucide-react · stroke-width 1.75"
                    code={`<Icon icon={Mic} size="md" />`}
                >
                    <div className="grid grid-cols-9 gap-3 w-full">
                        {ICONS.map(({ name, icon }) => (
                            <div
                                key={name}
                                className="flex flex-col items-center gap-1 p-2 border border-border text-accent"
                            >
                                <Icon icon={icon} size="lg" />
                                <span className="text-[8px] text-text-muted font-mono uppercase tracking-[1px]">
                                    {name}
                                </span>
                            </div>
                        ))}
                    </div>
                </ShowcaseCard>
            </div>
        </section>
    );
}

export default PrimitivesTextSection;
