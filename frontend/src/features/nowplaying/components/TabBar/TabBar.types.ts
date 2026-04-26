import type { SpotifyTab } from '../../types';

export interface TabBarProps {
    activeTab: SpotifyTab;
    onTabChange: (tab: SpotifyTab) => void;
}
