import { ReactElement } from 'react';
import { Button } from '../../primitives/Button';
import { ShowcaseCard } from '../ShowcaseCard';

export function ButtonsSection(): ReactElement {
    return (
        <section id="buttons" className="flex flex-col gap-4">
            <div>
                <h2 className="text-[12px] text-text font-mono mb-1">Buttons</h2>
                <p className="text-[10px] text-text-secondary font-mono">
                    primary · secondary · ghost · danger — sizes sm / md
                </p>
            </div>
            <div className="grid grid-cols-3 gap-3">
                <ShowcaseCard
                    label="PRIMARY MD"
                    code={`<Button variant="primary">VERBINDEN</Button>`}
                >
                    <Button variant="primary">VERBINDEN</Button>
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
                <ShowcaseCard
                    label="GHOST SM"
                    code={`<Button variant="ghost" size="sm">CANCEL</Button>`}
                >
                    <Button variant="ghost" size="sm">
                        CANCEL
                    </Button>
                </ShowcaseCard>
                <ShowcaseCard label="DISABLED" code={`<Button disabled>DISABLED</Button>`}>
                    <Button disabled>DISABLED</Button>
                </ShowcaseCard>
            </div>
        </section>
    );
}
