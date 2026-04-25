import type { ReactElement } from 'react';
import type { NavItem, NavGroup } from './Showcase.types';

export function buildNavItems(
    items: NavItem[],
    activeSection: string,
    onClick: (id: string) => void,
    onKeyDown: (e: React.KeyboardEvent<HTMLButtonElement>, id: string) => void,
): ReactElement[] {
    const result: ReactElement[] = [];
    let lastGroup: NavGroup = undefined as unknown as NavGroup;

    items.forEach((item) => {
        const isNewGroup = item.group !== lastGroup;
        lastGroup = item.group;

        if (isNewGroup && item.group !== null) {
            result.push(
                <div
                    key={`grp-${item.group}`}
                    className="text-[7px] text-text-muted uppercase tracking-[2px] font-mono px-2 pt-3 pb-1 border-t border-border mt-1"
                    aria-hidden="true"
                >
                    {item.group}
                </div>,
            );
        }

        const isActive = activeSection === item.id;
        const indent = item.group !== null ? 'pl-3' : '';

        result.push(
            <button
                key={item.id}
                onClick={() => onClick(item.id)}
                onKeyDown={(e) => onKeyDown(e, item.id)}
                className={[
                    'w-full text-left text-[9px] uppercase tracking-[1px] font-mono',
                    'px-2 py-[5px] border transition-all duration-[200ms]',
                    'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent',
                    indent,
                    isActive
                        ? 'text-accent border-accent-dim bg-[rgba(76,168,232,0.08)]'
                        : 'text-text-muted border-transparent hover:text-text-secondary hover:border-border',
                ].join(' ')}
                aria-current={isActive ? 'true' : undefined}
            >
                {item.label}
            </button>,
        );
    });

    return result;
}
