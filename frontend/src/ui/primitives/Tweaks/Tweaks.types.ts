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

export interface ToggleRowProps {
    label: string;
    value: boolean;
    onToggle: () => void;
}

export interface SwatchButtonProps {
    hue: number;
    active: boolean;
    onSelect: () => void;
}
