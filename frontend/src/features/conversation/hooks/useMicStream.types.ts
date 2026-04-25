export interface UseMicStreamOptions {
    /** When true, stop sending audio (e.g. while JARVIS is speaking). */
    paused: boolean;
}

export interface UseMicStreamReturn {
    isCapturing: boolean;
}

/**
 * Module-level singleton state for the mic capture session.
 * Lives outside the React component to survive StrictMode mount/unmount/remount.
 */
export interface MicSessionState {
    audioCtx: AudioContext | null;
    sourceNode: MediaStreamAudioSourceNode | null;
    // ScriptProcessorNode is deprecated but has the widest browser support
    // for real-time raw PCM access without an AudioWorklet bundler setup.
    // eslint-disable-next-line @typescript-eslint/no-deprecated
    processorNode: ScriptProcessorNode | null;
    silentGain: GainNode | null;
    stream: MediaStream | null;
    unlockHandler: (() => void) | null;
    /** True while getUserMedia + AudioContext setup is in-flight. */
    starting: boolean;
    /** Active mount count; start fires at 1, stop fires at 0. */
    refCount: number;
    firstFrameLogged: boolean;
    /** Ref forwarded from the hook so onaudioprocess can read paused state. */
    pausedRef: React.RefObject<boolean> | null;
}
