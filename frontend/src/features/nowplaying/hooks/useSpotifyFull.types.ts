import type {
    SpotifyTab,
    LibraryView,
    SpotifySearchResults,
    SpotifyQueueItem,
} from '../types';

export interface UseSpotifyFullReturn {
    activeTab: SpotifyTab;
    setActiveTab: (tab: SpotifyTab) => void;

    libraryView: LibraryView;
    openPlaylist: (id: string) => void;
    openAlbum: (id: string) => void;
    goBack: () => void;

    searchQuery: string;
    setSearchQuery: (q: string) => void;
    searchResults: SpotifySearchResults | undefined;
    isLoadingSearch: boolean;

    queue: SpotifyQueueItem[];
    isLoadingQueue: boolean;

    addToQueue: (uri: string) => void;
    playContext: (contextUri: string, offsetUri?: string) => void;
    playUris: (uris: string[]) => void;

    premiumError: boolean;
    isLoadingLibrary: boolean;
}
