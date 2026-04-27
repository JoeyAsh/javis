import type { PanelMode } from '@common/types';
import type { DeviceEvent, LedgerKind, LedgerKindCounts, VoiceComposerStatus } from '../../types';

export interface LedgerInspectorProps {
    mode?: PanelMode;
}

export interface LedgerHeaderProps {
    voiceComposerStatus: VoiceComposerStatus;
    counts24h: LedgerKindCounts;
}

export interface LedgerFilterRowProps {
    kindFilter: LedgerKind[];
    sinceMs: number | null;
    onKindsChange: (kinds: LedgerKind[]) => void;
    onSinceChange: (ms: number | null) => void;
}

export interface LedgerEventListProps {
    events: DeviceEvent[];
}

export interface LedgerEventGroupProps {
    correlationId: string | null;
    events: DeviceEvent[];
}
