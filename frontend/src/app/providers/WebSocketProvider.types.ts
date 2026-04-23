import type { ReactNode } from 'react';

export interface WebSocketProviderProps {
    children: ReactNode;
    url?: string;
}
