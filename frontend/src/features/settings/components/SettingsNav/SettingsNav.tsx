import type { ReactElement } from 'react';
import type { SectionId } from '../../types';
import type { SettingsNavProps } from './SettingsNav.types';

const SECTIONS: ReadonlyArray<{ id: SectionId; label: string }> = [
    { id: 'audio', label: 'Audio' },
    { id: 'display', label: 'Display' },
    { id: 'voice', label: 'Voice' },
    { id: 'repositories', label: 'Repositories' },
    { id: 'persona', label: 'Persona' },
];

export function SettingsNav({ activeSection, onSelect }: SettingsNavProps): ReactElement {
    return (
        <nav className="w-[140px] flex-shrink-0 border-r border-border py-3 bg-black/15">
            {SECTIONS.map((s) => (
                <button
                    key={s.id}
                    type="button"
                    onClick={() => onSelect(s.id)}
                    className={[
                        'block w-full text-left bg-transparent border-none',
                        'border-l-2 cursor-pointer font-mono text-[11px] tracking-[0.08em]',
                        'px-[14px] py-2 transition-colors duration-150',
                        activeSection === s.id
                            ? 'bg-accent/10 border-l-accent text-accent'
                            : 'border-l-transparent text-text-secondary hover:text-accent-bright hover:bg-accent/5',
                    ].join(' ')}
                >
                    {s.label}
                </button>
            ))}
        </nav>
    );
}

export default SettingsNav;
