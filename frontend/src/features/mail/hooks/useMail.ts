import { useAppSelector } from '@app';
import { useStreamMailQuery } from '../mailApi';
import {
    selectMailMessages,
    selectMailUnreadCount,
    selectMailDraft,
    selectMailHasLiveData,
} from '../mailSelectors';
import type { UseMailReturn } from './useMail.types';

export function useMail(): UseMailReturn {
    // Side-effect: binds the WS subscription lifetime to this component's mount.
    useStreamMailQuery();

    const messages = useAppSelector(selectMailMessages);
    const unreadCount = useAppSelector(selectMailUnreadCount);
    const draft = useAppSelector(selectMailDraft);
    const hasLiveData = useAppSelector(selectMailHasLiveData);

    return { messages, unreadCount, draft, hasLiveData };
}
