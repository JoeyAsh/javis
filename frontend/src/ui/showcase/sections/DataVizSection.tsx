import { ReactElement } from 'react';
import { Sparkline } from '../../primitives/Sparkline';
import { ProgressBar } from '../../primitives/ProgressBar';
import { Pill } from '../../primitives/Pill';
import { Metric } from '../../primitives/Metric';
import { Label } from '../../primitives/Label';
import { ShowcaseCard } from '../ShowcaseCard';

const CPU_DATA = [18, 16, 14, 12, 14, 10, 8, 11, 6, 9, 5, 7, 11, 8, 6];
const TEMP_DATA = [14, 13, 11, 12, 9, 7, 5, 4, 3, 2, 1, 2, 4, 6, 8];

export function DataVizSection(): ReactElement {
    return (
        <section id="dataviz" className="flex flex-col gap-4">
            <div>
                <h2 className="text-[12px] text-text font-mono mb-1">Data Visualisation</h2>
                <p className="text-[10px] text-text-secondary font-mono">
                    Sparkline · ProgressBar · Pill · Metric · Label
                </p>
            </div>
            <div className="grid grid-cols-3 gap-3">
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
                            <Label>CPU TEMP</Label>
                            <Metric value={87} unit="°C" warn />
                        </div>
                        <Sparkline data={TEMP_DATA} variant="warn" />
                    </div>
                </ShowcaseCard>
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
                <ShowcaseCard label="PILL VARIANTS" code={`<Pill variant="ok">ONLINE</Pill>`}>
                    <div className="flex flex-wrap gap-2 justify-center">
                        <Pill>DEFAULT</Pill>
                        <Pill variant="ok">ONLINE</Pill>
                        <Pill variant="warn">WARN</Pill>
                        <Pill variant="err">ERROR</Pill>
                        <Pill variant="info">INFO</Pill>
                    </div>
                </ShowcaseCard>
                <ShowcaseCard label="METRIC VARIANTS" code={`<Metric value="12.3" unit="Mb/s" />`}>
                    <div className="flex flex-col gap-2 items-center">
                        <Metric value="42" unit="%" />
                        <Metric value="87" unit="°C" warn />
                        <Metric value="12.3" unit="Mb/s" small />
                    </div>
                </ShowcaseCard>
                <ShowcaseCard
                    label="LABEL VARIANTS"
                    code={`<Label>LABEL</Label>\n<Label dim>DIM</Label>`}
                >
                    <div className="flex flex-col gap-2 items-center">
                        <Label>LABEL DEFAULT</Label>
                        <Label dim>LABEL DIM</Label>
                    </div>
                </ShowcaseCard>
            </div>
        </section>
    );
}
