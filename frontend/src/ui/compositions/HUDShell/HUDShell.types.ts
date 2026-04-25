import type { ReactNode, CSSProperties } from 'react';

export interface HUDShellProps {
    topbar?: ReactNode;
    orb?: ReactNode;
    dock?: ReactNode;
    scene?: {
        grid?: boolean;
        stars?: boolean;
        scanlines?: boolean;
    };
    viewportCorners?: boolean;
    reactor?: boolean;
    idle?: boolean;
    working?: boolean;
    children?: ReactNode;
    className?: string;
    style?: CSSProperties;
}
