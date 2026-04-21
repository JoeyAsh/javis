import { ReactElement } from 'react';
import { Label } from '../../primitives/Label';
import { Metric } from '../../primitives/Metric';
import { Mono } from '../../primitives/Mono';
import { BrandMark } from '../../primitives/BrandMark';
import { ShowcaseCard } from '../ShowcaseCard';

export function TypographySection(): ReactElement {
    return (
        <section id="typography" className="flex flex-col gap-4">
            <div>
                <h2 className="text-[12px] text-text font-mono mb-1">Typography</h2>
                <p className="text-[10px] text-text-secondary font-mono">
                    JetBrains Mono only. Label · Metric · Mono · BrandMark
                </p>
            </div>
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
        </section>
    );
}
