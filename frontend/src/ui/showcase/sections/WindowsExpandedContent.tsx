import type { ReactElement } from 'react';
import { Label } from '../../primitives/Label';
import type { WindowsExpandedContentProps } from './WindowsExpandedContent.types';

export function WindowsExpandedContent({ label }: WindowsExpandedContentProps): ReactElement {
    return (
        <div className="flex flex-col items-center justify-center h-full p-4 gap-2.5">
            <span className="text-[8px] tracking-[3px] uppercase text-[var(--accent)] font-mono">
                UNDOCKED
            </span>
            <Label>{label}</Label>
            <span className="text-[10px] text-text-secondary text-center font-mono">
                Drag header to move · resize via edges and corners · click ⊞ in header to dock back
            </span>
        </div>
    );
}

export default WindowsExpandedContent;
