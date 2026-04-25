export type PttState = 'idle' | 'holding' | 'flash';

export interface UsePushToTalkOptions {
    enabled: boolean;
}

export interface UsePushToTalkReturn {
    pttState: PttState;
    handlePressStart: () => void;
    handlePressEnd: () => void;
}
