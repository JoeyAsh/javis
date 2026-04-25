import type { ReactElement } from 'react';
import type { PanelContentRenderProps } from '../../window/Window';
import { WindowsCompactContent } from './WindowsCompactContent';
import { WindowsExpandedContent } from './WindowsExpandedContent';

export function makeRenderer(label: string): (props: PanelContentRenderProps) => ReactElement {
    return function Renderer({ mode }: PanelContentRenderProps): ReactElement {
        if (mode === 'expanded') return <WindowsExpandedContent label={label} />;
        return <WindowsCompactContent label={label} />;
    };
}
