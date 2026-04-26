import { useCallback } from 'react';
import type { ReactElement } from 'react';
import { useSpotifyFull } from '../../hooks/useSpotifyFull';
import { NowPlayingStrip } from '../NowPlayingStrip';
import { TabBar } from '../TabBar';
import { LibraryTab } from '../LibraryTab';
import { SearchTab } from '../SearchTab';
import { QueueTab } from '../QueueTab';
import type { SpotifyTab } from '../../types';
import type { SpotifyFullPanelProps } from './SpotifyFullPanel.types';

export function SpotifyFullPanel({ track, onCmd }: SpotifyFullPanelProps): ReactElement {
    const { activeTab, setActiveTab } = useSpotifyFull();

    const handleTabChange = useCallback(
        (tab: SpotifyTab): void => {
            setActiveTab(tab);
        },
        [setActiveTab],
    );

    return (
        <div className="flex flex-col h-full overflow-hidden font-[var(--font)]">
            <NowPlayingStrip track={track} onCmd={onCmd} />
            <TabBar activeTab={activeTab} onTabChange={handleTabChange} />
            {activeTab === 'library' && <LibraryTab />}
            {activeTab === 'search' && <SearchTab />}
            {activeTab === 'queue' && <QueueTab />}
        </div>
    );
}

export default SpotifyFullPanel;
