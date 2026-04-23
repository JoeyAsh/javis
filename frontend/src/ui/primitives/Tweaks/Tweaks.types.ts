export interface TweaksState {
    hue: number;
    glow: number;
    scan: boolean;
    grid: boolean;
    rings: boolean;
    particles: boolean;
    idleDim: boolean;
}

export interface TweaksProps {
    open: boolean;
    tweaks: TweaksState;
    onChange: (next: TweaksState) => void;
    className?: string;
}
