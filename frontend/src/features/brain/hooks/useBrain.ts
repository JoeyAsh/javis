import { useCallback } from 'react';
import { useAppDispatch, useAppSelector } from '@app';
import { useStreamBrainInspectorQuery, sendLedgerQuery } from '../brainApi';
import {
    selectVoiceComposerStatus,
    selectLedgerRecent,
    selectCounts24h,
    selectKindFilter,
    selectSinceFilter,
} from '../brainSelectors';
import { setKindFilter, setSinceFilter } from '../brainSlice';
import type { LedgerKind, LedgerQueryRequest } from '../types';
import type { UseBrainReturn } from './useBrain.types';

export function useBrain(): UseBrainReturn {
    useStreamBrainInspectorQuery();

    const dispatch = useAppDispatch();
    const voiceComposerStatus = useAppSelector(selectVoiceComposerStatus);
    const filteredEvents = useAppSelector(selectLedgerRecent);
    const counts24h = useAppSelector(selectCounts24h);
    const kindFilter = useAppSelector(selectKindFilter);
    const sinceFilter = useAppSelector(selectSinceFilter);

    const setKinds = useCallback(
        (kinds: LedgerKind[]) => {
            dispatch(setKindFilter(kinds));
        },
        [dispatch],
    );

    const setSince = useCallback(
        (ms: number | null) => {
            dispatch(setSinceFilter(ms));
        },
        [dispatch],
    );

    const requestLedgerQuery = useCallback(
        (request: LedgerQueryRequest) => {
            sendLedgerQuery(request);
        },
        [],
    );

    return {
        voiceComposerStatus,
        filteredEvents,
        counts24h,
        kindFilter,
        sinceFilter,
        setKinds,
        setSince,
        requestLedgerQuery,
    };
}
