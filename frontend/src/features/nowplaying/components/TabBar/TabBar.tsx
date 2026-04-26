import type { ReactElement } from 'react';
import type { SpotifyTab } from '../../types';
import type { TabBarProps } from './TabBar.types';
import styles from './TabBar.module.css';

const TABS: { id: SpotifyTab; label: string }[] = [
    { id: 'library', label: 'LIBRARY' },
    { id: 'search', label: 'SEARCH' },
    { id: 'queue', label: 'QUEUE' },
];

export function TabBar({ activeTab, onTabChange }: TabBarProps): ReactElement {
    return (
        <div className="flex gap-1 flex-shrink-0 mb-2">
            {TABS.map(({ id, label }) => (
                <button
                    key={id}
                    type="button"
                    className={`${styles.tab}${activeTab === id ? ` ${styles.tabActive}` : ''}`}
                    onClick={() => onTabChange(id)}
                    aria-pressed={activeTab === id}
                    aria-label={label}
                >
                    {label}
                </button>
            ))}
        </div>
    );
}

export default TabBar;
