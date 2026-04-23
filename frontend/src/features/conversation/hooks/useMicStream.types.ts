export interface UseMicStreamOptions {
    /** When true, stop sending audio (e.g. while JARVIS is speaking). */
    paused: boolean;
}

export interface UseMicStreamReturn {
    isCapturing: boolean;
}
