import { ReactElement, ReactNode } from 'react';
import { Panel } from '../primitives/Panel';
import { CornerBrackets } from '../primitives/CornerBrackets';

export interface GlassCardProps {
    title?: string;
    children?: ReactNode;
    focused?: boolean;
    className?: string;
    bodyClassName?: string;
}

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
