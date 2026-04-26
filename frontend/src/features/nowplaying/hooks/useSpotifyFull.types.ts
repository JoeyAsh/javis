import type {
    SpotifyTab,
    LibraryView,
    SpotifySearchResults,
    SpotifyQueueItem,
    SpotifyPlaylist,
    SpotifyLibraryPage,
} from '../types';

export interface UseSpotifyFullReturn {
    activeTab: SpotifyTab;
    setActiveTab: (tab: SpotifyTab) => void;

    libraryView: LibraryView;
    openPlaylist: (id: string, uri: string) => void;
    openAlbum: (id: string, uri: string) => void;
    goBack: () => void;

    /** Playlists page fetched with LIBRARY_PAGE_LIMIT — shared with LibraryTab */
    playlistsPage: SpotifyLibraryPage<SpotifyPlaylist> | undefined;
    selectedPlaylistUri: string | null;
    /** Album URI for the currently-open album-tracks view — for playContext calls */
    selectedAlbumUri: string | null;

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
