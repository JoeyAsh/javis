import { type ReactElement } from 'react';
import { Panel } from '../../primitives/Panel';
import { CornerBrackets } from '../../primitives/CornerBrackets';
import type { GlassCardProps } from './GlassCard.types';

function cn(...parts: (string | undefined | false)[]): string {
    return parts.filter(Boolean).join(' ');
}

export function GlassCard({
    title,
    children,
    focused = false,
    className,
    bodyClassName,
}: GlassCardProps): ReactElement {
    return (
        <CornerBrackets focused={focused} className={cn('inline-block', className)}>
            <Panel title={title} focused={focused} className={bodyClassName}>
                {children}
            </Panel>
        </CornerBrackets>
    );
}

export default GlassCard;
