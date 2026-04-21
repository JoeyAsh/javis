import { useState, type ReactElement } from 'react';
import { GridBackground } from '../primitives/GridBackground';
import { BrandMark } from '../primitives/BrandMark';
import { OverviewSection } from './sections/OverviewSection';
import { TokensSection } from './sections/TokensSection';
import { PrimitivesTextSection } from './sections/PrimitivesTextSection';
import { PrimitivesChromeSection } from './sections/PrimitivesChromeSection';
import { PrimitivesInteractiveSection } from './sections/PrimitivesInteractiveSection';
import { OrbSection } from './sections/OrbSection';
import { CompositionsSection } from './sections/CompositionsSection';
import { WindowsSection } from './sections/WindowsSection';
import { DevOverlaysSection } from './sections/DevOverlaysSection';
import { useShowcaseSfx } from './ShowcaseSfxRoot';

/* ---- Nav definition ---- */

type NavGroup = 'TOKENS' | 'PRIMITIVES' | 'COMPOSITIONS' | 'DEV' | null;

interface NavItem {
    id: string;
    label: string;
    group: NavGroup;
}

const NAV: NavItem[] = [
    { id: 'overview', label: 'OVERVIEW', group: null },
    { id: 'tokens', label: 'TOKENS', group: 'TOKENS' },
    { id: 'primitives-text', label: 'TEXT & DATA', group: 'PRIMITIVES' },
    { id: 'chrome', label: 'CHROME', group: 'PRIMITIVES' },
    { id: 'primitives-interactive', label: 'INTERACTIVE', group: 'PRIMITIVES' },
    { id: 'orb', label: 'ORB', group: 'PRIMITIVES' },
    { id: 'compositions', label: 'COMPOSITIONS', group: 'COMPOSITIONS' },
    { id: 'windows', label: 'WINDOWS', group: 'COMPOSITIONS' },
    { id: 'dev-overlays', label: 'DEV TOOLS', group: 'DEV' },
];

/* ---- Showcase root ---- */

export function Showcase(): ReactElement {
    const [activeSection, setActiveSection] = useState<string>('overview');
    const { isMuted, toggleMute } = useShowcaseSfx();

    function handleNavClick(id: string): void {
        setActiveSection(id);
        const el = document.getElementById(id);
        if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }

    function handleNavKeyDown(e: React.KeyboardEvent<HTMLButtonElement>, id: string): void {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            handleNavClick(id);
        }
    }

    return (
        <div className="min-h-screen bg-bg text-text font-mono relative">
            {/* Page-level backdrop */}
            <GridBackground />

            {/* Sidebar nav */}
            <nav
                className="fixed top-0 left-0 bottom-0 w-[132px] flex flex-col gap-0 p-3 border-r border-border z-[30] overflow-y-auto"
                style={{ background: 'rgba(5,5,8,0.88)', backdropFilter: 'blur(12px)' }}
            >
                <div className="mb-5">
                    <BrandMark />
                </div>

                {buildNavItems(NAV, activeSection, handleNavClick, handleNavKeyDown)}

                <div className="mt-auto pt-3 flex flex-col gap-2">
                    <button
                        onClick={toggleMute}
                        data-sfx-hover="button"
                        className={[
                            'w-full text-left text-[9px] uppercase tracking-[1px] font-mono',
                            'px-2 py-[5px] border transition-all duration-[200ms]',
                            'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent',
                            isMuted
                                ? 'text-text-muted border-transparent hover:text-text-secondary hover:border-border'
                                : 'text-accent border-accent-dim bg-[rgba(76,168,232,0.08)]',
                        ].join(' ')}
                        aria-pressed={!isMuted}
                        aria-label={isMuted ? 'Unmute SFX' : 'Mute SFX'}
                    >
                        {isMuted ? 'SFX ◯' : 'SFX ◉'}
                    </button>
                    <span className="text-[8px] text-text-muted uppercase tracking-[1px] px-2">
                        v0.1.0
                    </span>
                </div>
            </nav>

            {/* Main content */}
            <main className="ml-[132px] p-8 flex flex-col gap-16">
                <OverviewSection />
                <TokensSection />
                <PrimitivesTextSection />
                <PrimitivesChromeSection />
                <PrimitivesInteractiveSection />
                <OrbSection />
                <CompositionsSection />
                <WindowsSection />
                <DevOverlaysSection />
            </main>
        </div>
    );
}

/* ---- Nav builder ---- */

function buildNavItems(
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

export default Showcase;
