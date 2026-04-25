import type { AgendaEvent } from '../../types';
import type { PanelMode } from '@common/types';

export interface AgendaPanelProps {
    /** Optional prop override for tests / storybook. Skips live WS subscription. */
    events?: AgendaEvent[];
    mode?: PanelMode;
}
