import type { ReactNode } from 'react';

export interface GlowFrameProps {
    children: ReactNode;
    breathe?: boolean;
    strong?: boolean;
    className?: string;
}
