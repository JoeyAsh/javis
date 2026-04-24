import { type ReactElement } from 'react';
import { cx } from '@common/utils/cx';
import { Panel } from '../../primitives/Panel';
import { CornerBrackets } from '../../primitives/CornerBrackets';
import type { GlassCardProps } from './GlassCard.types';

export function GlassCard({
    title,
    children,
    focused = false,
    className,
    bodyClassName,
}: GlassCardProps): ReactElement {
    return (
        <CornerBrackets focused={focused} className={cx('inline-block', className)}>
            <Panel title={title} focused={focused} className={bodyClassName}>
                {children}
            </Panel>
        </CornerBrackets>
    );
}

export default GlassCard;
