import type { ReactElement } from 'react';
import { Label } from '../../primitives/Label';

interface WindowsCompactContentProps {
    label: string;
}

export function WindowsCompactContent({ label }: WindowsCompactContentProps): ReactElement {
    return (
        <div className="flex items-center justify-center h-full p-2 gap-1.5">
            <span className="text-[8px] tracking-[3px] uppercase text-text-muted font-mono">
                DOCKED
            </span>
            <Label dim>{label}</Label>
        </div>
    );
}

export default WindowsCompactContent;
