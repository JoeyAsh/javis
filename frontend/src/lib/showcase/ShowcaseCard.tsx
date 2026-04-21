import { ReactElement, ReactNode } from 'react';

export interface ShowcaseCardProps {
    label: string;
    code: string;
    children: ReactNode;
    dark?: boolean;
}

export function ShowcaseCard({
    label,
    code,
    children,
    dark = false,
}: ShowcaseCardProps): ReactElement {
    return (
        <div
            className="flex flex-col gap-3 p-4 border border-border rounded-[2px]"
            style={{ background: dark ? 'rgba(5,5,8,0.9)' : 'rgba(13,13,20,0.75)' }}
        >
            <div className="flex items-center justify-between">
                <span className="text-[9px] uppercase tracking-[1px] text-text-secondary font-mono">
                    {label}
                </span>
            </div>
            <div className="flex items-center justify-center min-h-[48px] py-2">{children}</div>
            <pre className="text-[9px] text-accent-bright font-mono overflow-x-auto whitespace-pre-wrap leading-relaxed">
                <code>{code}</code>
            </pre>
        </div>
    );
}
